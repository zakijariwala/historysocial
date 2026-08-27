"""Collect cover images once, with a licence, and never a human figure.

    python tools/fetch_images.py --plan          show what it would collect
    python tools/fetch_images.py --collect       collect and write images/bank.yaml

Everything here exists to enforce two rules that cannot be enforced later:

  RULE 3  No human figures in any image, ever. Not the Fourteen, not anonymous
          faces, not crowds. This tool rejects a candidate whose museum record
          carries any human tag, whose title reads as a human subject, or whose
          classification is one that depicts people. A rejected candidate is
          logged with its reason, so the filter can be audited.

  LICENCE No licence recorded at collection time means the image is unusable.
          The Metropolitan Museum's Open Access set is CC0, and the tool checks
          the `isPublicDomain` flag on every object individually rather than
          trusting the search that returned it.

Mood tags come from a FIXED vocabulary and are assigned by the query that
found the image, never invented per item:

    severe | ornate | desolate | bright | dense | still
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANK_DIR = ROOT / "images" / "bank"
BANK_YAML = ROOT / "images" / "bank.yaml"
REJECTS = ROOT / "images" / "rejected.yaml"

MET = "https://collectionapi.metmuseum.org/public/collection/v1"
USER_AGENT = "history-social/1.0 (cover bank; contact: repo owner)"

MOODS = ("severe", "ornate", "desolate", "bright", "dense", "still")

# Anything here in a tag, a title or a classification disqualifies the image.
# Deliberately broad. A false rejection costs one candidate; a false accept
# breaks the one rule the account cannot walk back.
HUMAN_TERMS = {
    "man", "men", "woman", "women", "child", "children", "boy", "girl",
    "figure", "figures", "portrait", "portraits", "self-portrait", "face",
    "faces", "head", "heads", "nude", "nudes", "saint", "saints", "virgin",
    "christ", "jesus", "madonna", "angel", "angels", "prophet", "king",
    "queen", "emperor", "sultan", "shah", "prince", "princess", "soldier",
    "soldiers", "warrior", "warriors", "horseman", "rider", "hunter",
    "musician", "dancer", "crowd", "family", "mother", "father", "couple",
    "people", "person", "body", "hand", "hands", "arm", "leg", "skeleton",
    "skull", "mummy", "deity", "god", "goddess", "buddha", "apostle",
    "martyr", "shepherd", "servant", "slave", "scribe", "reciting",
}

CLASSIFICATION_BLOCK = re.compile(
    r"sculpture|figur|portrait|miniature|paintings", re.I)

# query -> the moods that query's results carry, and the subject it satisfies.
# Subjects are the permitted list and nothing else: botanical plates,
# manuscript folios, astronomical diagrams, tilework, textiles, maps,
# doorways, stone, empty ground.
QUERIES = [
    {"q": "tile", "params": {"medium": "Ceramics"},
     "subject": "tilework", "moods": ["ornate", "dense"], "take": 4},
    {"q": "calligraphy folio", "params": {"departmentId": 14},
     "subject": "manuscript folio", "moods": ["severe", "still"], "take": 4},
    {"q": "astrolabe", "params": {},
     "subject": "astronomical diagram", "moods": ["severe", "dense"], "take": 2},
    {"q": "botanical", "params": {"departmentId": 9},
     "subject": "botanical plate", "moods": ["bright", "still"], "take": 3},
    {"q": "flowers plate", "params": {"departmentId": 9},
     "subject": "botanical plate", "moods": ["bright", "dense"], "take": 2},
    {"q": "carpet", "params": {"departmentId": 14},
     "subject": "textile", "moods": ["ornate", "dense"], "take": 3},
    {"q": "map", "params": {},
     "subject": "map", "moods": ["desolate", "severe"], "take": 3},
    {"q": "mihrab architectural stone", "params": {"departmentId": 14},
     "subject": "stone", "moods": ["severe", "still"], "take": 3},
    {"q": "landscape", "params": {"departmentId": 9},
     "subject": "empty ground", "moods": ["desolate", "still"], "take": 3},
    {"q": "herbal", "params": {"departmentId": 9},
     "subject": "botanical plate", "moods": ["bright", "still"], "take": 3},
    {"q": "leaf study drawing", "params": {"departmentId": 11},
     "subject": "botanical plate", "moods": ["still", "bright"], "take": 2},
    {"q": "celestial globe", "params": {},
     "subject": "astronomical diagram", "moods": ["severe", "dense"], "take": 2},
    {"q": "world map engraving", "params": {},
     "subject": "map", "moods": ["desolate", "severe"], "take": 3},
    {"q": "rocks study", "params": {"departmentId": 11},
     "subject": "stone", "moods": ["severe", "desolate"], "take": 2},
    {"q": "doorway", "params": {},
     "subject": "doorway", "moods": ["severe", "still"], "take": 2},
    {"q": "quran folio", "params": {"departmentId": 14},
     "subject": "manuscript folio", "moods": ["severe", "ornate"], "take": 3},
]


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _human_word(word: str) -> bool:
    """Match singular and plural. `musicians` has to trip `musician`."""
    if word in HUMAN_TERMS:
        return True
    for suffix in ("s", "es"):
        if word.endswith(suffix) and word[:-len(suffix)] in HUMAN_TERMS:
            return True
    return False


def human_reason(obj: dict) -> str | None:
    """Why this object may show a person, or None when it is clean."""
    tags = [t.get("term", "") for t in (obj.get("tags") or [])]
    for tag in tags:
        for word in re.findall(r"[a-z']+", tag.lower()):
            if _human_word(word):
                return f"tag: {tag}"
    for field in ("title", "objectName", "creditLine"):
        for word in re.findall(r"[a-z']+", str(obj.get(field, "")).lower()):
            if _human_word(word):
                return f"{field}: {obj.get(field)}"
    cls = str(obj.get("classification", ""))
    if CLASSIFICATION_BLOCK.search(cls):
        return f"classification: {cls}"
    return None


def candidates(spec: dict, seen: set[int]) -> list[dict]:
    params = {"q": spec["q"], "hasImages": "true", **spec["params"]}
    url = f"{MET}/search?" + urllib.parse.urlencode(params)
    try:
        ids = get_json(url).get("objectIDs") or []
    except Exception as exc:
        print(f"  search failed: {exc}", file=sys.stderr)
        return []
    out, rejected = [], []
    # Cap the scan. Some department searches return thousands of ids, and each
    # one costs an object call; the bank does not need the whole museum.
    for oid in ids[:80]:
        if len(out) >= spec["take"]:
            break
        if oid in seen:
            continue
        try:
            obj = get_json(f"{MET}/objects/{oid}")
        except Exception:
            continue
        time.sleep(0.05)
        if not obj.get("isPublicDomain"):
            rejected.append((oid, obj.get("title", ""), "not public domain"))
            continue
        if not (obj.get("primaryImage") or obj.get("primaryImageSmall")):
            rejected.append((oid, obj.get("title", ""), "no full-size image"))
            continue
        reason = human_reason(obj)
        if reason:
            rejected.append((oid, obj.get("title", ""), f"human figure risk: {reason}"))
            continue
        seen.add(oid)
        out.append({"obj": obj, "spec": spec})
    spec["_rejected"] = rejected
    return out


def download(url: str, dest: Path) -> int:
    # Met image URLs carry en dashes and spaces in some filenames, which the
    # HTTP layer cannot encode on its own.
    url = urllib.parse.quote(url, safe=":/?&=%")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((1600, 1600))
        img.save(dest, "JPEG", quality=88)
        return dest.stat().st_size
    except Exception:
        dest.write_bytes(data)
        return len(data)


def yaml_escape(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def existing_entries() -> list[dict]:
    """What images/bank.yaml already holds, so --append does not lose a review.

    A human's `review: approved` is the most expensive field in the file. It
    survives every later collection run.
    """
    if not BANK_YAML.exists():
        return []
    import yaml

    doc = yaml.safe_load(BANK_YAML.read_text(encoding="utf-8")) or {}
    out = []
    for img_id, rec in (doc.get("images") or {}).items():
        rec = dict(rec)
        rec["id"] = img_id
        out.append(rec)
    return out


def write_bank(entries: list[dict]) -> None:
    lines = [
        "# The cover bank. One entry per image, collected once.",
        "#",
        "# Every entry carries a licence recorded AT COLLECTION TIME. An entry",
        "# without one is unusable and the renderer refuses it.",
        "#",
        "# figures: none  is asserted by tools/fetch_images.py, which rejects any",
        "# object whose museum record carries a human tag, title or classification.",
        "# `review: pending` means no human has looked at the image itself yet.",
        "# tools/lint_post.py fails a post whose cover is still pending, so a",
        "# machine's judgement about Rule 3 never reaches a published slide.",
        "#",
        "# moods come from the fixed vocabulary and nothing else:",
        "#   severe | ornate | desolate | bright | dense | still",
        "",
        "images:",
    ]
    for e in entries:
        lines += [
            f'  {e["id"]}:',
            f'    file: {e["file"]}',
            f'    title: {yaml_escape(e["title"])}',
            f'    creator: {yaml_escape(e["creator"])}',
            f'    date: {yaml_escape(e["date"])}',
            f'    source: {yaml_escape(e["source"])}',
            f'    source_url: {yaml_escape(e["source_url"])}',
            f'    licence: {yaml_escape(e["licence"])}',
            f'    subject: {yaml_escape(e["subject"])}',
            f'    moods: [{", ".join(e["moods"])}]',
            "    figures: none",
            f'    figures_checked_by: {e.get("figures_checked_by", "tools/fetch_images.py")}',
            f'    review: {e.get("review", "pending")}',
            "",
        ]
    BANK_YAML.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="collect cover images with licences")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--append", action="store_true",
                    help="keep what images/bank.yaml already holds, reviews included")
    ap.add_argument("--queries", help="comma-separated subjects to run, default all")
    a = ap.parse_args()

    if a.plan or not a.collect:
        for spec in QUERIES:
            print(f'{spec["subject"]:<22} take {spec["take"]}  '
                  f'moods {", ".join(spec["moods"]):<18} q={spec["q"]}')
        print("\nMet Open Access only. Rijksmuseum, Wellcome, the Biodiversity")
        print("Heritage Library and David Rumsey need a key or a per-item licence")
        print("check, so they are added by hand. See DECISIONS.md.")
        return 0

    BANK_DIR.mkdir(parents=True, exist_ok=True)
    entries = existing_entries() if a.append else []
    seen = {int(e["id"].split("-")[1]) for e in entries if e["id"].startswith("met-")}
    rejects = []
    wanted = [q.strip() for q in a.queries.split(",")] if a.queries else None
    for spec in QUERIES:
        if wanted and spec["subject"] not in wanted:
            continue
        print(f'{spec["subject"]}...', flush=True)
        for hit in candidates(spec, seen):
            obj, s = hit["obj"], hit["spec"]
            img_id = f'met-{obj["objectID"]}'
            dest = BANK_DIR / f"{img_id}.jpg"
            try:
                # The small derivative is ~1200px on the long edge, which is
                # enough for a 1080px canvas and spares a 40MB original.
                size = download(obj.get("primaryImageSmall") or obj["primaryImage"],
                                dest)
            except Exception as exc:
                print(f"  download failed {img_id}: {exc}", file=sys.stderr)
                continue
            entries.append({
                "id": img_id,
                "file": f"bank/{img_id}.jpg",
                "title": obj.get("title") or "untitled",
                "creator": obj.get("artistDisplayName") or "unrecorded",
                "date": obj.get("objectDate") or "undated",
                "source": "The Metropolitan Museum of Art, Open Access",
                "source_url": obj.get("objectURL", ""),
                "licence": "CC0 1.0 (Met Open Access, isPublicDomain = true)",
                "subject": s["subject"],
                "moods": [m for m in s["moods"] if m in MOODS],
            })
            print(f'  {img_id}  {size:>8,} bytes  {entries[-1]["title"][:52]}',
                  flush=True)
        rejects += [(spec["subject"], *r) for r in spec.get("_rejected", [])]

    write_bank(entries)
    lines = ["# Candidates the filter refused, and why. Kept so Rule 3 is auditable.",
             "rejected:"]
    for subject, oid, title, reason in rejects:
        lines += [f"  - object: {oid}",
                  f"    subject: {yaml_escape(subject)}",
                  f"    title: {yaml_escape(title)}",
                  f"    reason: {yaml_escape(reason)}"]
    REJECTS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{len(entries)} images in the bank, {len(rejects)} rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
