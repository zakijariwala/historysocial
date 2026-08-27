"""Search the local sources and report PRINTED PAGE NUMBERS.

    python tools/lookup.py "Musa b. Ja'far"
    python tools/lookup.py "Waqifa" --source irshad --context 1
    python tools/lookup.py "nineteen years" --exact

The query is expanded into a spelling family by sourcelib.loose_pattern, so
one search finds Ja'far, Jafar and Jaʿfar. No embeddings. No vector store.
Character rules only, so every match is explainable by reading the regex.

ripgrep does the scanning when a real `rg` binary is on PATH; otherwise the
same regex runs in Python over the same files. Both paths report identical
hits, so a machine without ripgrep is slower and never wrong.

Every hit prints as:

    SRC-IRS-003  p. 212   (pdf 216)  ...the matching line...

`p. ?` means the page carries no printed number. A hit there can be read, but
it can never become a verified claim: Rule 2 requires a printed page.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from bisect import bisect_right
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcelib import fold_preserving, loose_pattern  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEXT = ROOT / "sources" / "text"
PAGES = ROOT / "sources" / "pages"
MANIFEST = ROOT / "sources" / "manifest.yaml"


def load_index(key: str):
    path = PAGES / f"{key}.pages.jsonl"
    if not path.exists():
        return [], []
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln]
    return [r["start"] for r in rows], rows


def registry() -> dict[str, dict]:
    """text_key -> manifest record. Empty when a volume is not registered."""
    if not MANIFEST.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    out = {}
    for source_key, rec in (doc.get("sources") or {}).items():
        rec = dict(rec)
        rec["source_key"] = source_key
        out[rec.get("text_key", source_key)] = rec
    return out


def rg_binary() -> str | None:
    """A real ripgrep executable, or None. A shell alias does not count."""
    path = shutil.which("rg")
    if not path or not Path(path).is_file():
        return None
    try:
        subprocess.run([path, "--version"], capture_output=True, timeout=10, check=True)
    except Exception:
        return None
    return path


def scan_with_rg(binary: str, pattern: str, files: list[Path]):
    cmd = [binary, "--byte-offset", "--no-heading", "--with-filename",
           "--ignore-case", "--no-line-number", "--text",
           "-e", pattern] + [str(f) for f in files]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stderr.strip() or "ripgrep failed")
    for line in proc.stdout.splitlines():
        parts = line.split(":")
        # <drive>:<path>:<byte offset>:<text> on Windows, <path>:... elsewhere
        for cut in (3, 2):
            if len(parts) > cut and parts[cut - 1].isdigit():
                path_s = ":".join(parts[:cut - 1])
                yield Path(path_s).stem, int(parts[cut - 1]), ":".join(parts[cut:])
                break


def scan_with_python(pattern: str, files: list[Path]):
    rx = re.compile(pattern, re.IGNORECASE)
    for f in files:
        body = f.read_text(encoding="utf-8", errors="replace")
        # Search a length-preserving fold of the text, report the original.
        # Howard prints Mūsā and Hārūn; a query for Musa has to find them, and
        # folding one character to one keeps every offset honest.
        haystack = fold_preserving(body)
        for m in rx.finditer(haystack):
            line_start = body.rfind("\n", 0, m.start()) + 1
            line_end = body.find("\n", m.end())
            line_end = len(body) if line_end == -1 else line_end
            # The page index speaks bytes, so a character index has to be
            # converted before it can be looked up in it.
            byte_offset = len(body[:m.start()].encode("utf-8"))
            yield f.stem, byte_offset, body[line_start:line_end]


def run(query: str, source: str | None, exact: bool, context: int, limit: int) -> int:
    pattern = re.escape(query) if exact else loose_pattern(query)
    files = sorted(TEXT.glob("*.txt"))
    if source:
        files = [f for f in files if source.lower() in f.stem.lower()]
    if not files:
        print("no extracted text. run: python tools/extract_pages.py", file=sys.stderr)
        return 1

    reg = registry()
    # ripgrep is used only for an exact query. The expanded search has to fold
    # diacritics in the text as well as the query, and ripgrep cannot fold the
    # haystack, so that path stays in Python where the fold is possible.
    binary = rg_binary() if exact else None
    hits = (scan_with_rg(binary, pattern, files) if binary
            else scan_with_python(pattern, files))

    shown = 0
    caches: dict[str, tuple] = {}
    for key, offset, text in hits:
        if key not in caches:
            caches[key] = load_index(key)
        starts, rows = caches[key]
        if not starts:
            continue
        row = rows[max(bisect_right(starts, offset) - 1, 0)]
        printed = row["printed_page"] or "?"
        rec = reg.get(key, {})
        label = rec.get("source_key", key[:22])
        flag = "  [index-only]" if rec.get("role") == "index-only" else ""
        snippet = " ".join(text.split())[:130]
        print(f"{label:<12} p. {printed:<6} (pdf {row['pdf_page']:>4})  {snippet}{flag}")
        if context:
            page = (TEXT / f"{key}.txt").read_text(encoding="utf-8").split("\f")
            body = page[row["pdf_page"] - 1] if row["pdf_page"] <= len(page) else ""
            for ln in [l.strip() for l in body.splitlines() if l.strip()][:context * 4]:
                print(f"    | {ln[:118]}")
        shown += 1
        if shown >= limit:
            print(f"... stopped at {limit} hits (--limit to raise)")
            break
    if shown == 0:
        print("no hits")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="search local sources by printed page")
    ap.add_argument("query")
    ap.add_argument("--source", help="restrict to volumes whose key contains this")
    ap.add_argument("--exact", action="store_true", help="no spelling expansion")
    ap.add_argument("--context", type=int, default=0, help="print N*4 lines of the page")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()
    return run(a.query, a.source, a.exact, a.context, a.limit)


if __name__ == "__main__":
    raise SystemExit(main())
