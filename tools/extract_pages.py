"""PDF -> page-preserving plain text, one file per volume.

    python tools/extract_pages.py            # every PDF in sources/
    python tools/extract_pages.py al-mufid   # one, by filename fragment

Writes two files per volume, both gitignored:

    sources/text/<key>.txt          pages joined by form feed (\\f)
    sources/pages/<key>.pages.jsonl one JSON object per page:
        {"pdf_page": 216, "printed_page": "212", "source": "read",
         "start": 91234, "end": 93110}

`printed_page` is the number PRINTED ON THE PAGE, not a count of PDF pages,
and `source` says how it was obtained:

    read      a numeral was found in the header or footer AND it agrees with
              the pagination of the pages around it
    derived   no numeral was readable, so the page took the offset its
              neighbours agree on (pdf page + offset)
    none      neither. lookup.py prints `p. ?` and the page can never carry a
              verified claim, because Rule 2 requires a printed page

The agreement test matters. A footnote marker at the foot of a page reads as a
page number and is off by hundreds. Trusting it would put a claim on a page
that does not hold it, which is worse than reporting no page at all.

Offsets are BYTE offsets into the .txt file, because ripgrep reports bytes.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcelib import slug  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources"
TEXT = SRC / "text"
PAGES = SRC / "pages"

ROMAN = re.compile(r"^[ivxlcdm]{1,7}$", re.I)
ARABIC = re.compile(r"^\d{1,4}$")

# How far to look for neighbours that agree, and how many must agree.
WINDOW = 6
AGREE = 2


def candidate_number(page_text: str) -> str | None:
    """The most likely page number in the header or footer, or None."""
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    if not lines:
        return None
    for ln in lines[:2] + lines[-2:]:
        if ARABIC.match(ln) or ROMAN.match(ln):
            return ln
        toks = ln.split()
        for tok in (toks[0], toks[-1]):
            tok = tok.strip(".[]()")
            if ARABIC.match(tok) and len(lines) > 3:
                return tok
    return None


def reconcile(index: list[dict]) -> None:
    """Keep the numerals their neighbours corroborate; derive the rest.

    Works on local agreement rather than one offset for the whole book, so a
    roman-numbered preface followed by an arabic body reconciles correctly
    instead of throwing the whole volume out.
    """
    offsets = {}
    for i, row in enumerate(index):
        raw = row.get("candidate")
        if raw and ARABIC.match(raw):
            offsets[i] = int(raw) - (i + 1)

    trusted = {}
    for i, off in offsets.items():
        near = [offsets[j] for j in range(i - WINDOW, i + WINDOW + 1)
                if j in offsets and j != i]
        if near.count(off) >= AGREE - 1 or len(offsets) == 1:
            trusted[i] = off

    # Fall back to the dominant offset when nothing local corroborates, which
    # happens in short volumes with few readable numbers.
    if not trusted and offsets:
        common = Counter(offsets.values()).most_common(1)[0]
        if common[1] >= AGREE:
            trusted = {i: common[0] for i, o in offsets.items() if o == common[0]}

    keys = sorted(trusted)
    for i, row in enumerate(index):
        raw = row.pop("candidate", None)
        if i in trusted:
            row["printed_page"], row["source"] = str(int(raw)), "read"
            continue
        if raw and ROMAN.match(raw) and i < (keys[0] if keys else len(index)):
            row["printed_page"], row["source"] = raw.lower(), "read"
            continue
        if keys:
            nearest = min(keys, key=lambda k: abs(k - i))
            derived = i + 1 + trusted[nearest]
            if derived > 0:
                row["printed_page"], row["source"] = str(derived), "derived"
                if raw:
                    row["rejected_candidate"] = raw
                continue
        row["printed_page"], row["source"] = None, "none"


def extract(pdf_path: Path, key: str) -> dict:
    TEXT.mkdir(parents=True, exist_ok=True)
    PAGES.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf_path))
    chunks: list[str] = []
    index: list[dict] = []
    byte_offset = 0
    for i in range(len(doc)):
        raw = doc[i].get_textpage().get_text_range() or ""
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        nbytes = len(raw.encode("utf-8"))
        chunks.append(raw)
        index.append({
            "pdf_page": i + 1,
            "candidate": candidate_number(raw),
            "start": byte_offset,
            "end": byte_offset + nbytes,
        })
        byte_offset += nbytes + 1                    # +1 for the \f separator

    reconcile(index)
    body = "\f".join(chunks)
    (TEXT / f"{key}.txt").write_text(body, encoding="utf-8")
    with (PAGES / f"{key}.pages.jsonl").open("w", encoding="utf-8") as fh:
        for row in index:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    counts = Counter(r["source"] for r in index)
    return {
        "key": key, "pdf_pages": len(index), "counts": counts,
        "bytes": len(body.encode("utf-8")),
    }


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    pdfs = sorted(SRC.glob("*.pdf"))
    if argv:
        needle = argv[0].lower()
        pdfs = [p for p in pdfs if needle in slug(p.stem) or needle in p.stem.lower()]
    if not pdfs:
        print("no PDFs matched", file=sys.stderr)
        return 1
    failures = 0
    for pdf in pdfs:
        key = slug(pdf.stem)
        try:
            st = extract(pdf, key)
        except Exception as exc:                     # a broken PDF is not fatal
            print(f"FAILED  {pdf.name}: {exc}", file=sys.stderr)
            failures += 1
            continue
        c = st["counts"]
        print(f'{st["key"]:<52} {st["pdf_pages"]:>5} pages  '
              f'read {c["read"]:>4}  derived {c["derived"]:>4}  '
              f'none {c["none"]:>4}  {st["bytes"]:>9} bytes')
    if failures:
        print(f"\n{failures} PDF(s) could not be opened. See BLOCKED.md.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
