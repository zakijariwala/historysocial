"""Write the human review into the cover bank.

    python tools/apply_review.py            # show what would change
    python tools/apply_review.py --write    # do it

Reads images/review.yaml. Approved entries get `review: approved`, the subject
and moods a person assigned, and the reviewer's name. Rejected entries leave
the bank entirely and their files are deleted, so a post cannot reach a
rejected image by a typo.

Anything in the bank that the review file does not mention stays `pending`,
which means the linter will refuse to render a post that uses it. Silence is
never approval.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "images" / "bank.yaml"
REVIEW = ROOT / "images" / "review.yaml"
REJECTED = ROOT / "images" / "rejected-by-review.yaml"
MOODS = ("severe", "ornate", "desolate", "bright", "dense", "still")


def quote(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="apply images/review.yaml to the bank")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    bank = yaml.safe_load(BANK.read_text(encoding="utf-8")) or {}
    review = yaml.safe_load(REVIEW.read_text(encoding="utf-8")) or {}
    images = bank.get("images") or {}
    approve = review.get("approve") or {}
    reject = review.get("reject") or {}
    who = review.get("reviewed_by", "unnamed")

    kept, dropped, pending = {}, {}, []
    for img_id, rec in images.items():
        if img_id in reject:
            dropped[img_id] = reject[img_id]
            continue
        if img_id in approve:
            decision = approve[img_id]
            bad = [m for m in decision.get("moods", []) if m not in MOODS]
            if bad:
                print(f"{img_id}: {bad} is outside the mood vocabulary", file=sys.stderr)
                return 2
            rec = dict(rec)
            rec["subject"] = decision.get("subject", rec.get("subject"))
            rec["moods"] = decision.get("moods", rec.get("moods"))
            rec["review"] = "approved"
            rec["reviewed_by"] = who
            kept[img_id] = rec
            continue
        pending.append(img_id)
        kept[img_id] = rec

    print(f"{len(kept) - len(pending)} approved, {len(dropped)} rejected, "
          f"{len(pending)} left pending")
    for img_id in pending:
        print(f"  pending: {img_id}  ({images[img_id].get('title', '')[:48]})")
    if not a.write:
        print("\nnothing written. Re-run with --write.")
        return 0

    lines = [
        "# The cover bank. One entry per image, collected once, then reviewed.",
        "#",
        "# licence      recorded at collection time. No licence means unusable.",
        "# figures      none. Asserted by the collector's filter over the museum",
        "#              record, then confirmed by the person named in reviewed_by.",
        "# review       approved | pending. tools/lint_post.py refuses to render",
        "#              a post whose cover is still pending, so a machine's",
        "#              judgement about Rule 3 never reaches a published slide.",
        "# moods        severe | ornate | desolate | bright | dense | still",
        "",
        "images:",
    ]
    for img_id, rec in kept.items():
        lines.append(f"  {img_id}:")
        for key in ("file", "title", "creator", "date", "source", "source_url",
                    "licence", "subject"):
            if rec.get(key) is not None:
                lines.append(f"    {key}: {quote(rec[key])}")
        lines.append(f'    moods: [{", ".join(rec.get("moods") or [])}]')
        lines.append("    figures: none")
        lines.append(f'    figures_checked_by: {quote(rec.get("figures_checked_by", "tools/fetch_images.py"))}')
        lines.append(f'    review: {rec.get("review", "pending")}')
        if rec.get("reviewed_by"):
            lines.append(f'    reviewed_by: {quote(rec["reviewed_by"])}')
        lines.append("")
    BANK.write_text("\n".join(lines), encoding="utf-8")

    out = ["# Images a person looked at and refused, with the reason.",
           f"# Reviewer: {who}", "rejected:"]
    for img_id, why in dropped.items():
        out += [f"  {img_id}: {quote(' '.join(str(why).split()))}"]
        path = ROOT / "images" / "bank" / f"{img_id}.jpg"
        if path.exists():
            path.unlink()
    REJECTED.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {BANK.name} and {REJECTED.name}; deleted {len(dropped)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
