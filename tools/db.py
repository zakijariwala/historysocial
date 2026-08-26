"""The claim and post database. Library plus command line.

    python tools/db.py migrate
    python tools/db.py claim-add --subject "Musa b. Ja'far" \
        --assertion "died in Baghdad in the custody of al-Sindi b. Shahik" \
        --hijri 183 --ce 799 --source SRC-IRS-003 --page 441 --pillar collision
    python tools/db.py verify CLM-0001 --by zaki
    python tools/db.py unverified [--pillar collision]
    python tools/db.py coverage
    python tools/db.py post-create --id musa-custody --pillar collision ...
    python tools/db.py drafts
    python tools/db.py metrics musa-custody --shares 412 --likes 900 --saves 300

WHAT THIS TOOL REFUSES TO DO

  verify without a page          Rule 2. A page number is what makes a claim
                                 checkable by somebody who does not trust you.
  verify against a TODO edition  sources/manifest.yaml still has no edition
                                 statement for that source, so "p. 441" names
                                 no particular book.
  verify against an index        SRC-TAB-040 is an index volume. It can point
                                 at a page; it cannot be the source of one.
  verify a claim whose source is not registered in the manifest at all.

Nothing here writes an assertion, a date, or a page on its own. Every value
comes from the command line, which means from a human who read the page.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "claims.db"
MIGRATIONS = ROOT / "migrations"
MANIFEST = ROOT / "sources" / "manifest.yaml"

PILLARS = ("collision", "fact_panel", "map", "calendar", "number", "date_pair")
TEMPLATES = ("cover", "question", "body", "closing")
STATUSES = ("draft", "ready", "posted")


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply every migration not yet recorded. Safe to run repeatedly."""
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_migration (
                      filename TEXT PRIMARY KEY, applied_on TEXT NOT NULL)""")
    done = {r["filename"] for r in conn.execute("SELECT filename FROM schema_migration")}
    applied = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
        if path.name not in done:
            conn.execute("INSERT INTO schema_migration VALUES (?, ?)",
                         (path.name, dt.date.today().isoformat()))
            applied.append(path.name)
    conn.commit()
    return applied


def manifest_sources() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    doc = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    return doc.get("sources") or {}


def verification_block(source_key: str, page: str | None) -> str | None:
    """Why this claim may NOT be verified, or None when it may."""
    if not page or not str(page).strip():
        return "no page. Rule 2: no page number means it cannot be verified."
    sources = manifest_sources()
    if not sources:
        return "sources/manifest.yaml is missing or unreadable."
    rec = sources.get(source_key)
    if rec is None:
        return (f"{source_key} is not registered in sources/manifest.yaml. "
                f"Register the volume before citing it.")
    if str(rec.get("edition", "")).strip().upper().startswith("TODO"):
        return (f"{source_key} still has no edition statement in the manifest. "
                f'Fill `edition:` from the copy in hand, then verify again.')
    if rec.get("role") == "index-only":
        return (f"{source_key} is an index volume. It can tell you which page "
                f"holds a thing; it cannot itself be the source of a claim.")
    if rec.get("usable") is False:
        return f"{source_key} is marked unusable in the manifest."
    return None


def next_id(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT id FROM claim ORDER BY id DESC LIMIT 1").fetchone()
    n = int(row["id"].split("-")[1]) + 1 if row else 1
    return f"CLM-{n:04d}"


# --------------------------------------------------------------------------
# commands

def cmd_migrate(conn, a):
    applied = migrate(conn)
    print("applied: " + (", ".join(applied) if applied else "nothing new"))
    return 0


def cmd_claim_add(conn, a):
    cid = a.id or next_id(conn)
    if a.pillar not in PILLARS:
        print(f"pillar must be one of {', '.join(PILLARS)}", file=sys.stderr)
        return 2
    sources = manifest_sources()
    if sources and a.source not in sources:
        print(f"warning: {a.source} is not in sources/manifest.yaml. The row is "
              f"stored, but it can never be verified until the volume is registered.",
              file=sys.stderr)
    edition = a.edition or (sources.get(a.source, {}) or {}).get("edition") or "TODO"
    conn.execute(
        """INSERT INTO claim (id, subject, assertion, hijri_date, ce_date,
                              source_key, edition, page, pillar, dispute_note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (cid, a.subject, a.assertion, a.hijri, a.ce, a.source, edition,
         a.page, a.pillar, a.dispute))
    conn.commit()
    print(f"{cid}  unverified  {a.source} p. {a.page or '-'}")
    return 0


def cmd_verify(conn, a):
    row = conn.execute("SELECT * FROM claim WHERE id = ?", (a.id,)).fetchone()
    if row is None:
        print(f"no claim {a.id}", file=sys.stderr)
        return 2
    page = a.page if a.page is not None else row["page"]
    block = verification_block(row["source_key"], page)
    if block:
        print(f"REFUSED {a.id}: {block}", file=sys.stderr)
        return 1
    conn.execute("""UPDATE claim SET verified = 1, verified_by = ?, verified_on = ?,
                                     page = ?, edition = ?
                    WHERE id = ?""",
                 (a.by, dt.date.today().isoformat(), page,
                  a.edition or manifest_sources()[row["source_key"]]["edition"],
                  a.id))
    conn.commit()
    print(f"{a.id}  VERIFIED  {row['source_key']} p. {page}  by {a.by}")
    return 0


def cmd_unverified(conn, a):
    sql = "SELECT * FROM claim WHERE verified = 0"
    args: list = []
    if a.pillar:
        sql += " AND pillar = ?"
        args.append(a.pillar)
    rows = conn.execute(sql + " ORDER BY id", args).fetchall()
    for r in rows:
        page = r["page"] or "NO PAGE"
        print(f'{r["id"]}  {r["pillar"]:<10} {r["source_key"]:<12} p. {page:<8} '
              f'{r["assertion"][:70]}')
    print(f"\n{len(rows)} unverified")
    return 0


def cmd_coverage(conn, a):
    print(f'{"pillar":<12} {"verified":>8} {"unverified":>11} {"total":>7}')
    total_v = total_u = 0
    for pillar in PILLARS:
        v = conn.execute("SELECT COUNT(*) c FROM claim WHERE pillar=? AND verified=1",
                         (pillar,)).fetchone()["c"]
        u = conn.execute("SELECT COUNT(*) c FROM claim WHERE pillar=? AND verified=0",
                         (pillar,)).fetchone()["c"]
        total_v, total_u = total_v + v, total_u + u
        print(f"{pillar:<12} {v:>8} {u:>11} {v + u:>7}")
    print(f'{"ALL":<12} {total_v:>8} {total_u:>11} {total_v + total_u:>7}')

    print("\nposts")
    for r in conn.execute("""SELECT p.id, p.status, p.pillar,
                                    (SELECT COUNT(*) FROM slide s WHERE s.post_id=p.id) n,
                                    (SELECT COUNT(*) FROM post_claim pc JOIN claim c
                                       ON c.id=pc.claim_id
                                     WHERE pc.post_id=p.id AND c.verified=1) vc
                             FROM post p ORDER BY p.id"""):
        print(f'{r["id"]:<24} {r["status"]:<7} {r["pillar"]:<11} '
              f'{r["n"]:>3} slides  {r["vc"]:>3} verified claims')
    return 0


def cmd_post_create(conn, a):
    if a.pillar not in PILLARS:
        print(f"pillar must be one of {', '.join(PILLARS)}", file=sys.stderr)
        return 2
    conn.execute("""INSERT INTO post (id, pillar, running_head, cover_title,
                                      cover_image, ink, caption, mourning, status)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                 (a.id, a.pillar, a.running_head, a.cover_title, a.cover_image,
                  a.ink, a.caption, 1 if a.mourning else 0, "draft"))
    conn.commit()
    print(f"{a.id}  draft  {a.pillar}")
    return 0


def cmd_slide_set(conn, a):
    if a.template not in TEMPLATES:
        print(f"template must be one of {', '.join(TEMPLATES)}", file=sys.stderr)
        return 2
    body = a.body if a.body is not None else sys.stdin.read().strip()
    conn.execute("""INSERT INTO slide (post_id, position, template, body)
                    VALUES (?,?,?,?)
                    ON CONFLICT(post_id, position)
                    DO UPDATE SET template = excluded.template, body = excluded.body""",
                 (a.post, a.position, a.template, body))
    conn.commit()
    print(f"{a.post} slide {a.position} {a.template} ({len(body.split())} words)")
    return 0


def cmd_link(conn, a):
    for claim_id in a.claims:
        conn.execute("INSERT OR IGNORE INTO post_claim VALUES (?,?)", (a.post, claim_id))
    conn.commit()
    print(f"{a.post} <- {', '.join(a.claims)}")
    return 0


def cmd_status(conn, a):
    if a.status not in STATUSES:
        print(f"status must be one of {', '.join(STATUSES)}", file=sys.stderr)
        return 2
    conn.execute("UPDATE post SET status = ? WHERE id = ?", (a.status, a.post))
    conn.commit()
    print(f"{a.post} -> {a.status}")
    return 0


def cmd_drafts(conn, a):
    rows = conn.execute("SELECT * FROM post WHERE status = 'draft' ORDER BY id")
    for r in rows:
        n = conn.execute("SELECT COUNT(*) c FROM slide WHERE post_id=?",
                         (r["id"],)).fetchone()["c"]
        print(f'{r["id"]:<24} {r["pillar"]:<11} {n:>3} slides  {r["cover_title"]}')
    return 0


def cmd_metrics(conn, a):
    """Shares first. It is the number that predicts growth for this format."""
    fields, args = [], []
    for name in ("shares", "likes", "saves"):
        val = getattr(a, name)
        if val is not None:
            fields.append(f"{name} = ?")
            args.append(val)
    if not fields:
        for r in conn.execute("""SELECT id, shares, likes, saves FROM post
                                 WHERE status='posted' ORDER BY shares DESC"""):
            print(f'{r["id"]:<24} shares {str(r["shares"] or "-"):>6}  '
                  f'likes {str(r["likes"] or "-"):>6}  saves {str(r["saves"] or "-"):>6}')
        return 0
    args.append(a.post)
    conn.execute(f"UPDATE post SET {', '.join(fields)} WHERE id = ?", args)
    conn.commit()
    print(f"{a.post} metrics updated")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="claim and post database")
    ap.add_argument("--db", default=str(DB_PATH))
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("migrate").set_defaults(fn=cmd_migrate)

    p = sub.add_parser("claim-add")
    p.add_argument("--id")
    p.add_argument("--subject", required=True)
    p.add_argument("--assertion", required=True)
    p.add_argument("--hijri")
    p.add_argument("--ce")
    p.add_argument("--source", required=True, help="a key in sources/manifest.yaml")
    p.add_argument("--edition")
    p.add_argument("--page", help="the PRINTED page number")
    p.add_argument("--pillar", required=True, choices=PILLARS)
    p.add_argument("--dispute", help="where the chronicles disagree, name both")
    p.set_defaults(fn=cmd_claim_add)

    p = sub.add_parser("verify")
    p.add_argument("id")
    p.add_argument("--by", required=True)
    p.add_argument("--page")
    p.add_argument("--edition")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("unverified")
    p.add_argument("--pillar", choices=PILLARS)
    p.set_defaults(fn=cmd_unverified)

    sub.add_parser("coverage").set_defaults(fn=cmd_coverage)

    p = sub.add_parser("post-create")
    p.add_argument("--id", required=True)
    p.add_argument("--pillar", required=True, choices=PILLARS)
    p.add_argument("--running-head", required=True, dest="running_head")
    p.add_argument("--cover-title", required=True, dest="cover_title")
    p.add_argument("--cover-image", dest="cover_image")
    p.add_argument("--ink", required=True)
    p.add_argument("--caption", required=True)
    p.add_argument("--mourning", action="store_true")
    p.set_defaults(fn=cmd_post_create)

    p = sub.add_parser("slide-set")
    p.add_argument("--post", required=True)
    p.add_argument("--position", type=int, required=True)
    p.add_argument("--template", required=True, choices=TEMPLATES)
    p.add_argument("--body", help="omit to read the slide body from stdin")
    p.set_defaults(fn=cmd_slide_set)

    p = sub.add_parser("link")
    p.add_argument("--post", required=True)
    p.add_argument("claims", nargs="+")
    p.set_defaults(fn=cmd_link)

    p = sub.add_parser("status")
    p.add_argument("post")
    p.add_argument("status", choices=STATUSES)
    p.set_defaults(fn=cmd_status)

    sub.add_parser("drafts").set_defaults(fn=cmd_drafts)

    p = sub.add_parser("metrics")
    p.add_argument("post", nargs="?")
    p.add_argument("--shares", type=int)
    p.add_argument("--likes", type=int)
    p.add_argument("--saves", type=int)
    p.set_defaults(fn=cmd_metrics)

    return ap


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    a = build_parser().parse_args()
    conn = connect(a.db)
    if a.cmd != "migrate":
        migrate(conn)
    return a.fn(conn, a)


if __name__ == "__main__":
    raise SystemExit(main())
