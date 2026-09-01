"""The gates a post passes before anything renders.

    python tools/lint_post.py --post musa-custody
    python tools/lint_post.py --all-ready

render/render.py calls this first and renders nothing if it fails. The gates:

    slide 2 uses the question template
    slide count between 12 and 20
    a running head on every interior slide
    the post resolves to at least one VERIFIED claim
    zero [[NEEDS CLAIM: placeholders
    no cover image without a licence record
    no cover image whose Rule 3 check is still unreviewed
    mourning posts have a solid cover and greyscale tokens
    every prose rule in tools/lint_prose.py

Text overflow is not checked here. It is checked in the renderer, where the
text has actually been laid out, and it fails the build there.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import yaml  # noqa: E402

import db  # noqa: E402
from lint_prose import Finding, check_post, load  # noqa: E402

TOKENS = ROOT / "tokens" / "tokens.yaml"
BANK = ROOT / "images" / "bank.yaml"
MANIFEST = ROOT / "sources" / "manifest.yaml"


def gates(conn: sqlite3.Connection, post, slides, claims,
          allow_unreviewed_cover: bool) -> list[Finding]:
    out: list[Finding] = []
    tokens = yaml.safe_load(TOKENS.read_text(encoding="utf-8")) or {}

    verified = [c for c in claims if c["verified"]]
    if not verified:
        out.append(Finding("FAIL", None, "no-verified-claim",
                           f"{len(claims)} claims linked, none verified. A slide "
                           f"renders only from rows marked verified."))
    elif len(verified) < len(claims):
        unverified_ids = [c["id"] for c in claims if not c["verified"]]
        out.append(Finding("FAIL", None, "unverified-claims-linked",
                           f"{len(unverified_ids)} of {len(claims)} claims linked to this post "
                           f"are unverified ({', '.join(unverified_ids)}). Every linked claim "
                           f"must be verified before the post can render."))
    sources = (yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}).get(
        "sources", {}) if MANIFEST.exists() else {}
    for c in verified:
        if not (c["locator"] or "").strip():
            out.append(Finding("FAIL", None, "verified-without-locator",
                               f'{c["id"]} is verified with nothing to look it '
                               f"up by. Rule 2."))

        # A claim freezes its source's edition string at the moment it is
        # verified. Edit the manifest afterwards and every row stamped before
        # the edit still carries the old wording, so one post can cite two
        # editions of one book without any other check noticing.
        # A non-Shia source may be cited, never alone. The account is openly
        # Shia; a chronicle standing beside al-Mufid is an argument, a
        # chronicle standing alone is a different publication.
        if (sources.get(c["source_key"]) or {}).get("tradition") != "shia":
            block = db.hostile_witness_block(c["source_key"], c["assertion"],
                                             c["role"])
            if block:
                out.append(Finding("FAIL", None, "non-shia-authority",
                                   f'{c["id"]} rests on {c["source_key"]}: {block}'))
            # A hostile witness is cited against something. If the post carries
            # no Shia claim, the chronicle is not being argued with, it is
            # simply being believed.
            elif not any(
                (sources.get(o["source_key"]) or {}).get("tradition") == "shia"
                for o in verified):
                out.append(Finding("FAIL", None, "no-shia-authority",
                                   f'{c["id"]} is the hostile witness, and this post '
                                   f'carries no verified Shia claim for it to stand '
                                   f'against. A post cannot rest on the chronicle alone.'))

        registered = sources.get(c["source_key"])
        if registered is None:
            out.append(Finding("FAIL", None, "source-not-registered",
                               f'{c["id"]} cites {c["source_key"]}, which is not '
                               f"in sources/manifest.yaml."))
        elif str(registered.get("edition", "")) != str(c["edition"]):
            out.append(Finding("FAIL", None, "edition-drift",
                               f'{c["id"]} was verified against '
                               f'{str(c["edition"])[:40]!r}, and '
                               f'{c["source_key"]} now reads '
                               f'{str(registered.get("edition"))[:40]!r}. '
                               f"Re-run: tools/db.py verify {c['id']} --by <you>"))

    for s in slides:
        if s["template"] == "cover":
            continue
        if not post["running_head"].strip():
            out.append(Finding("FAIL", s["position"], "running-head",
                               "no running head, so a screenshot of this slide "
                               "carries nothing."))
            break

    if post["ink"] not in (tokens.get("inks") or {}):
        out.append(Finding("FAIL", None, "unknown-ink",
                           f'ink {post["ink"]!r} is not one of the five: '
                           f'{", ".join(tokens.get("inks", {}))}'))

    if post["mourning"]:
        if post["cover_image"]:
            out.append(Finding("FAIL", None, "mourning-cover",
                               "a mourning post takes a solid cover. Remove the "
                               "cover image."))
        mourning = tokens.get("mourning", {})
        if mourning.get("ornament", False):
            out.append(Finding("FAIL", None, "mourning-tokens",
                               "mourning tokens carry an ornament."))
        if str(mourning.get("ground", "")).lower() not in ("#14161a",):
            out.append(Finding("WARN", None, "mourning-tokens",
                               f'mourning ground is {mourning.get("ground")!r}. '
                               f"The greyscale pair is #14161A on #C9C6C1."))
    elif post["cover_image"]:
        bank = (yaml.safe_load(BANK.read_text(encoding="utf-8"))
                if BANK.exists() else {}) or {}
        entry = (bank.get("images") or {}).get(post["cover_image"])
        if entry is None:
            out.append(Finding("FAIL", None, "cover-not-in-bank",
                               f'{post["cover_image"]} is not in images/bank.yaml'))
        else:
            if not str(entry.get("licence", "")).strip():
                out.append(Finding("FAIL", None, "cover-licence",
                                   f'{post["cover_image"]} has no licence recorded. '
                                   f"No licence means unusable."))
            if entry.get("figures") != "none":
                out.append(Finding("FAIL", None, "cover-figures",
                                   f'{post["cover_image"]} does not record '
                                   f"figures: none. Rule 3 has no exceptions."))
            if entry.get("review") != "approved" and not allow_unreviewed_cover:
                out.append(Finding("FAIL", None, "cover-unreviewed",
                                   f'{post["cover_image"]} is still review: pending. '
                                   f"A filter decided there is no human figure in "
                                   f"it; a person has to agree before it posts. Set "
                                   f"review: approved in images/bank.yaml."))
            src = ROOT / "images" / str(entry.get("file", ""))
            if not src.exists():
                out.append(Finding("FAIL", None, "cover-missing-file",
                                   f"the bank names {src.name}, which is not there"))

    return out


def run(conn, post_id: str, allow_unreviewed_cover: bool) -> list[Finding]:
    post, slides, claims = load(conn, post_id)
    return (gates(conn, post, slides, claims, allow_unreviewed_cover)
            + check_post(post, slides, claims))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="the gates a post passes before rendering")
    ap.add_argument("--post")
    ap.add_argument("--all-ready", action="store_true")
    ap.add_argument("--db", default=str(ROOT / "claims.db"))
    ap.add_argument("--report", action="store_true", help="print findings, exit 0")
    ap.add_argument("--allow-unreviewed-cover", action="store_true",
                    help="scratch cover work only. Never for a post that ships.")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    if a.all_ready:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM post WHERE status = 'ready' ORDER BY id")]
    elif a.post:
        ids = [a.post]
    else:
        print("give --post or --all-ready", file=sys.stderr)
        return 2

    total_fail = 0
    for post_id in ids:
        findings = run(conn, post_id, a.allow_unreviewed_cover)
        fails = [f for f in findings if f.level == "FAIL"]
        warns = [f for f in findings if f.level == "WARN"]
        total_fail += len(fails)
        print(f"== {post_id}")
        for f in findings:
            print(f"   {f}")
        print(f"   {len(fails)} FAIL, {len(warns)} WARN")
    return 1 if total_fail and not a.report else 0


if __name__ == "__main__":
    raise SystemExit(main())
