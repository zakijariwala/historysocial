"""Index a plain-text source that arrived without page images.

    python tools/ingest_text.py openiti--tabari-tarikh-ara.txt --format openiti

tools/extract_pages.py handles PDFs. This handles the files fetch_sources.py
downloads, which are already text and therefore carry their pagination as
markers rather than as page breaks.

    --format openiti   OpenITI mARkdown. `PageV01P003` means volume 1,
                       printed page 3 OF THE EDITION THE FILE NAMES IN ITS OWN
                       #META# header. printed_page is written as "1:3".
    --format formfeed  pages already separated by \\f
    --format none      no pagination at all. Every page comes out as `p. ?`,
                       which means nothing in the file can ever be verified
                       from. Indexed anyway so it is searchable for leads.

Writes the same two files extract_pages.py writes, so lookup.py cannot tell
the difference.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcelib import slug  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources"
TEXT = SRC / "text"
PAGES = SRC / "pages"

MARKER = re.compile(r"PageV(\d+)P(\d+)")


def split_openiti(body: str) -> list[tuple[str | None, str]]:
    """(printed_page, text) pairs. A marker CLOSES the page it follows."""
    out, cursor = [], 0
    for m in MARKER.finditer(body):
        vol, page = int(m.group(1)), int(m.group(2))
        out.append((f"{vol}:{page}", body[cursor:m.start()]))
        cursor = m.end()
    tail = body[cursor:]
    if tail.strip():
        out.append((None, tail))
    return out


def split_formfeed(body: str) -> list[tuple[str | None, str]]:
    return [(None, chunk) for chunk in body.split("\f")]


def ingest(path: Path, fmt: str, key: str) -> dict:
    TEXT.mkdir(parents=True, exist_ok=True)
    PAGES.mkdir(parents=True, exist_ok=True)
    body = path.read_text(encoding="utf-8", errors="replace")
    if fmt == "openiti":
        pages = split_openiti(body)
    elif fmt == "formfeed":
        pages = split_formfeed(body)
    else:
        pages = [(None, body)]

    chunks, index, byte_offset = [], [], 0
    for i, (printed, text) in enumerate(pages):
        nbytes = len(text.encode("utf-8"))
        chunks.append(text)
        index.append({
            "pdf_page": i + 1,
            "printed_page": printed,
            "source": "read" if printed else "none",
            "start": byte_offset,
            "end": byte_offset + nbytes,
        })
        byte_offset += nbytes + 1
    joined = "\f".join(chunks)
    (TEXT / f"{key}.txt").write_text(joined, encoding="utf-8")
    with (PAGES / f"{key}.pages.jsonl").open("w", encoding="utf-8") as fh:
        for row in index:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"pages": len(index),
            "numbered": sum(1 for r in index if r["printed_page"]),
            "bytes": len(joined.encode("utf-8"))}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="index a plain-text source")
    ap.add_argument("filename", help="a file inside sources/")
    ap.add_argument("--format", default="openiti",
                    choices=("openiti", "formfeed", "none"))
    ap.add_argument("--key", help="text key; defaults to the slugged filename")
    a = ap.parse_args()

    path = SRC / a.filename
    if not path.exists():
        print(f"no such file: {path}", file=sys.stderr)
        return 1
    key = a.key or slug(path.stem)
    st = ingest(path, a.format, key)
    print(f'{key:<44} {st["pages"]:>6} pages  {st["numbered"]:>6} numbered  '
          f'{st["bytes"]:>10} bytes')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
