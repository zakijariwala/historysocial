"""Assemble site/data/ from the database and the rendered output.

    python tools/build_site.py                    # every ready post
    python tools/build_site.py --all              # every post that has renders
    python tools/build_site.py --ids a,b,c        # a named set
    python tools/build_site.py --preview --all-drafts   # writes the red banner

Ported from the hadith-social review surface, which is the same job on a
different corpus: show the cards that have been rendered, read each one beside
its caption, copy the caption, download the images, tick off what has been
posted by hand. Posting happens in the Instagram app; nothing here talks to
Instagram.

WHAT IS GENERATED

site/data/ and nothing else. It is wiped and rewritten on every build, so
never hand-edit anything inside it - change this file or the renderer instead.
Everything outside site/data/ is hand-written and is left alone.

THE CAPTION IS WRITTEN IN FULL

That is load-bearing, not laziness. iOS Safari honours
navigator.clipboard.writeText only when it is called synchronously inside the
tap handler, so the caption has to be in memory before the finger lands. See
site/app.js and DECISIONS.md #18.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
SITE = ROOT / "site"
DATA = SITE / "data"


def build(conn: sqlite3.Connection, renders: Path, rows: list[sqlite3.Row],
          preview_note: str | None) -> list[dict]:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)

    index: list[dict] = []
    for row in rows:
        post_id = row["id"]
        manifest_path = renders / post_id / "manifest.json"
        if not manifest_path.exists():
            print(f"  skip {post_id}: nothing rendered", file=sys.stderr)
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        dest = DATA / post_id
        dest.mkdir(parents=True, exist_ok=True)
        slides = []
        for slide in manifest["slides"]:
            shutil.copy2(renders / post_id / slide["png"], dest / slide["png"])
            slides.append(f'{post_id}/{slide["png"]}')

        zip_name = f"{post_id}.zip"
        with zipfile.ZipFile(DATA / zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
            for slide in manifest["slides"]:
                zf.write(renders / post_id / slide["png"], slide["png"])

        index.append({
            "id": post_id,
            "title": row["cover_title"],
            "label": row["running_head"],
            "pillar": row["pillar"],
            "ink": row["ink"],
            "occasion": "mourning" if row["mourning"] else "normal",
            "status": row["status"],
            "caption": row["caption"],
            "zip": zip_name,
            "slides": slides,
            "posted_on": row["posted_on"],
        })

    (DATA / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    # Absence of meta.json is the normal case. A production build writes none,
    # so the banner cannot linger by accident.
    if preview_note:
        (DATA / "meta.json").write_text(
            json.dumps({"unreviewed": True, "note": preview_note},
                       indent=2, ensure_ascii=False), encoding="utf-8")
    return index


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="assemble site/data/ for review")
    ap.add_argument("--db", default=str(ROOT / "claims.db"))
    ap.add_argument("--renders", default=str(OUT),
                    help="directory holding <post_id>/manifest.json")
    ap.add_argument("--ids", help="comma-separated post ids, in place of --all")
    ap.add_argument("--all", action="store_true",
                    help="every post that has renders, whatever its status")
    ap.add_argument("--all-drafts", action="store_true",
                    help="drafts too. Requires --preview: a draft has not "
                         "passed the linter and may carry placeholders.")
    ap.add_argument("--preview", action="store_true",
                    help="write data/meta.json, which shows the red banner")
    a = ap.parse_args()

    if a.all_drafts and not a.preview:
        print("--all-drafts needs --preview. A draft can carry [[NEEDS CLAIM]] "
              "placeholders, and an unbannered build of one is a trap.",
              file=sys.stderr)
        return 2

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    if a.ids:
        wanted = [s.strip() for s in a.ids.split(",") if s.strip()]
        marks = ",".join("?" * len(wanted))
        rows = conn.execute(
            f"SELECT * FROM post WHERE id IN ({marks}) ORDER BY id", wanted).fetchall()
        missing = set(wanted) - {r["id"] for r in rows}
        if missing:
            print(f"no such post: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    elif a.all or a.all_drafts:
        rows = conn.execute("SELECT * FROM post ORDER BY id").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM post WHERE status IN ('ready','posted') ORDER BY id").fetchall()

    note = None
    if a.preview:
        note = (f"Preview build, {dt.date.today().isoformat()}. These cards have "
                f"not all passed the linter and may carry placeholders. "
                f"Do not post from this build.")

    index = build(conn, Path(a.renders), rows, note)
    print(f"site/data/index.json: {len(index)} posts")
    for p in index:
        flag = " POSTED" if p["posted_on"] else ""
        print(f'  {p["id"]:<24} {p["status"]:<7} {len(p["slides"]):>3} slides{flag}')
    if not index:
        print("nothing to review. Render something first.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
