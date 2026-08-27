"""Load an essay file into the database.

    python tools/load_essay.py essays/musa-bridge.yaml
    python tools/load_essay.py essays/samples/*.yaml --db scratch.db

An essay file is the writing surface: one YAML file holding the post, its
slides in order, and the CANDIDATE claim rows the essay leans on. Loading is
idempotent, so editing prose and re-loading is the working loop.

Candidate claims arrive with verified = 0 and they stay there. This tool has
no flag that verifies anything. A claim becomes verified when a person opens
the book at the page and runs tools/db.py verify, and never before.
"""

from __future__ import annotations

import argparse
import glob
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from db import connect, migrate  # noqa: E402


def load_file(conn: sqlite3.Connection, path: Path) -> str:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    post = doc["post"]
    post_id = post["id"]

    conn.execute("DELETE FROM slide WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM post_claim WHERE post_id = ?", (post_id,))
    conn.execute(
        """INSERT INTO post (id, pillar, running_head, cover_title, cover_image,
                             ink, caption, mourning, status)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             pillar=excluded.pillar, running_head=excluded.running_head,
             cover_title=excluded.cover_title, cover_image=excluded.cover_image,
             ink=excluded.ink, caption=excluded.caption,
             mourning=excluded.mourning""",
        (post_id, post["pillar"], post["running_head"], post["cover_title"],
         post.get("cover_image"), post["ink"], post["caption"],
         1 if post.get("mourning") else 0, post.get("status", "draft")))

    for i, slide in enumerate(doc["slides"], start=1):
        body = slide.get("body")
        if slide["template"] == "cover" and not body:
            body = post["cover_title"]
        conn.execute("INSERT INTO slide (post_id, position, template, body) "
                     "VALUES (?,?,?,?)",
                     (post_id, i, slide["template"], body.strip()))

    for j, claim in enumerate(doc.get("claims") or [], start=1):
        claim_id = claim.get("id") or f"{post_id}-c{j:02d}"
        conn.execute(
            """INSERT INTO claim (id, subject, assertion, hijri_date, ce_date,
                                  source_key, edition, page, pillar, dispute_note)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 subject=excluded.subject, assertion=excluded.assertion,
                 hijri_date=excluded.hijri_date, ce_date=excluded.ce_date,
                 source_key=excluded.source_key, page=excluded.page,
                 pillar=excluded.pillar, dispute_note=excluded.dispute_note""",
            (claim_id, claim["subject"], claim["assertion"],
             str(claim.get("hijri") or "") or None,
             str(claim.get("ce") or "") or None,
             claim["source"], claim.get("edition", "TODO"),
             str(claim.get("page") or "") or None,
             claim.get("pillar", post["pillar"]), claim.get("dispute")))
        conn.execute("INSERT OR IGNORE INTO post_claim VALUES (?,?)",
                     (post_id, claim_id))

    conn.commit()
    return post_id


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="load an essay file into the database")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--db", default=str(ROOT / "claims.db"))
    a = ap.parse_args()

    conn = connect(a.db)
    migrate(conn)
    paths = [Path(p) for pattern in a.files for p in glob.glob(pattern)]
    if not paths:
        print("no files matched", file=sys.stderr)
        return 1
    for path in sorted(paths):
        post_id = load_file(conn, path)
        n = conn.execute("SELECT COUNT(*) FROM slide WHERE post_id = ?",
                         (post_id,)).fetchone()[0]
        c = conn.execute("SELECT COUNT(*) FROM post_claim WHERE post_id = ?",
                         (post_id,)).fetchone()[0]
        print(f"{post_id:<28} {n:>3} slides  {c:>3} candidate claims  <- {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
