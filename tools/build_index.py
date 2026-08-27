"""Assemble site/ from the database and the rendered output.

    python tools/build_index.py

Copies each rendered post into site/posts/<id>/, builds one zip per post, and
writes site/index.json, which is the only thing the frontend reads.

The caption is written into index.json in full. That is deliberate and it is
load-bearing: iOS Safari only honours navigator.clipboard.writeText inside a
tap handler with no await before it, so the caption has to be in memory before
the finger lands. See site/app.js.

Nothing here is uploaded from a developer machine. Actions runs it, and
Actions deploys the directory it produces.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
SITE = ROOT / "site"
POSTS = SITE / "posts"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    conn = sqlite3.connect(str(ROOT / "claims.db"))
    conn.row_factory = sqlite3.Row

    if POSTS.exists():
        shutil.rmtree(POSTS)
    POSTS.mkdir(parents=True, exist_ok=True)

    index = {"posts": [], "generated_from": "claims.db + out/"}
    for row in conn.execute("SELECT * FROM post ORDER BY id"):
        post_id = row["id"]
        rendered = OUT / post_id
        manifest_path = rendered / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        dest = POSTS / post_id
        dest.mkdir(parents=True, exist_ok=True)
        slides = []
        for slide in manifest["slides"]:
            shutil.copy2(rendered / slide["png"], dest / slide["png"])
            slides.append({"position": slide["position"],
                           "template": slide["template"],
                           "png": f'posts/{post_id}/{slide["png"]}'})
        shutil.copy2(manifest_path, dest / "manifest.json")

        zip_path = dest / f"{post_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for slide in manifest["slides"]:
                zf.write(rendered / slide["png"], slide["png"])
            zf.write(manifest_path, "manifest.json")

        index["posts"].append({
            "id": post_id,
            "title": row["cover_title"],
            "running_head": row["running_head"],
            "pillar": row["pillar"],
            "status": row["status"],
            "mourning": bool(row["mourning"]),
            "slide_count": len(slides),
            "caption": row["caption"],
            "zip": f"posts/{post_id}/{post_id}.zip",
            "slides": slides,
            "rendered_at": manifest["rendered_at"],
            "renderer_version": manifest["renderer_version"],
        })

    (SITE / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f'site/index.json: {len(index["posts"])} posts')
    for p in index["posts"]:
        print(f'  {p["id"]:<24} {p["status"]:<7} {p["slide_count"]:>3} slides')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
