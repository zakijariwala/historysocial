"""Render a post to 1080x1350 PNGs, or fail the whole post.

    python render/render.py --post musa-custody
    python render/render.py --all-ready
    python render/render.py --post musa-cover-test --db scratch.db --skip-lint

Jinja2 builds one HTML file per slide, headless Chromium screenshots it. The
PNG is output. The database and the render manifest are truth.

TWO THINGS THIS WILL NOT DO

  Partial output. Slides render into a temporary directory and move into
  out/<post>/ only when every slide of the post has succeeded. A carousel
  missing slide 9 is worse than a carousel that failed loudly.

  Shrink text to fit. If the measured text overflows its box the render
  fails with the slide number and the overflow in pixels. Text that does not
  fit is an editing problem, and the fix belongs in the database.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from render.duotone import duotone, halftone  # noqa: E402

RENDERER_VERSION = "1.0.0"
TOKENS = ROOT / "tokens" / "tokens.yaml"
TEMPLATES = ROOT / "templates"
BANK = ROOT / "images" / "bank.yaml"
OUT = ROOT / "out"

COVER_SUBLINE = "sourced to the printed page"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def font_url(rel: str) -> str:
    return (ROOT / rel).resolve().as_uri()


def post_row(conn: sqlite3.Connection, post_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM post WHERE id = ?", (post_id,)).fetchone()
    if row is None:
        raise SystemExit(f"no post {post_id}")
    return row


def slide_rows(conn: sqlite3.Connection, post_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM slide WHERE post_id = ? ORDER BY position", (post_id,)))


def resolve_cover(post: sqlite3.Row, tokens: dict, assets: Path,
                  screen: str) -> tuple[str | None, dict | None]:
    """Duotone the cover into `assets`, or return None for a solid cover.

    Mourning posts never take an image. That is not a fallback; a solid cover
    is the correct cover for a mourning post, for a number post, and for
    anything whose licence is not clean.
    """
    if post["mourning"] or not post["cover_image"]:
        return None, None
    bank = load_yaml(BANK).get("images", {})
    entry = bank.get(post["cover_image"])
    if entry is None:
        raise SystemExit(f'cover image {post["cover_image"]} is not in images/bank.yaml')
    if not str(entry.get("licence", "")).strip():
        raise SystemExit(f'cover image {post["cover_image"]} has no licence recorded')
    src = ROOT / "images" / entry["file"]
    if not src.exists():
        raise SystemExit(f"cover image file missing: {src}")

    ink = tokens["inks"][post["ink"]]
    ground = tokens["grounds"][tokens["normal"]["ground"]]
    size = (tokens["canvas"]["width"], tokens["canvas"]["height"])
    dst = assets / "cover.png"
    if screen == "halftone":
        halftone(src, dst, shadow=ink, highlight=ground,
                 dot=tokens["cover"]["halftone"]["dot"],
                 angle=tokens["cover"]["halftone"]["angle"],
                 gamma=tokens["cover"]["duotone"]["gamma"], size=size)
    else:
        duotone(src, dst, shadow=ink, highlight=ground,
                gamma=tokens["cover"]["duotone"]["gamma"], size=size)
    return dst.resolve().as_uri(), {
        "id": post["cover_image"], "file": entry["file"],
        "licence": entry["licence"], "source": entry.get("source"),
        "pass": screen, "shadow": ink, "highlight": ground,
    }


def render_post(conn: sqlite3.Connection, post_id: str, screen: str,
                out_root: Path = OUT) -> dict:
    tokens = load_yaml(TOKENS)
    post = post_row(conn, post_id)
    slides = slide_rows(conn, post_id)
    if not slides:
        raise SystemExit(f"{post_id} has no slides")

    mourning = bool(post["mourning"])
    ground = (tokens["mourning"]["ground"] if mourning
              else tokens["grounds"][tokens["normal"]["ground"]])
    ink = (tokens["mourning"]["ink"] if mourning else tokens["inks"][post["ink"]])

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      undefined=StrictUndefined, autoescape=True)
    fonts = {
        "serif_regular": font_url(tokens["fonts"]["serif"]["regular"]),
        "serif_italic": font_url(tokens["fonts"]["serif"]["italic"]),
        "grotesque_regular": font_url(tokens["fonts"]["grotesque"]["regular"]),
    }

    staging = Path(tempfile.mkdtemp(prefix=f"render-{post_id}-"))
    assets = staging / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    try:
        cover_url, cover_meta = resolve_cover(post, tokens, assets, screen)
        pages = []
        for slide in slides:
            html = env.get_template(f'{slide["template"]}.html').render(
                post=post, slide=slide, tokens=tokens, fonts=fonts,
                ground=ground, ink=ink, cover_image_url=cover_url,
                cover_subline=COVER_SUBLINE)
            page = staging / f'{slide["position"]:02d}.html'
            page.write_text(html, encoding="utf-8")
            pages.append((slide, page))

        shots = shoot(pages, tokens, staging)

        final = out_root / post_id
        if final.exists():
            shutil.rmtree(final)
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), str(final))
        staging = None  # moved
    finally:
        if staging is not None and Path(staging).exists():
            shutil.rmtree(staging, ignore_errors=True)

    manifest = {
        "post_id": post_id,
        "renderer_version": RENDERER_VERSION,
        "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pillar": post["pillar"],
        "status": post["status"],
        "running_head": post["running_head"],
        "cover_title": post["cover_title"],
        "caption": post["caption"],
        "mourning": bool(post["mourning"]),
        "tokens": {"ink": post["ink"], "ink_hex": ink, "ground_hex": ground,
                   "canvas": tokens["canvas"]},
        "cover_asset": cover_meta,
        "claims": [r["claim_id"] for r in conn.execute(
            "SELECT claim_id FROM post_claim WHERE post_id = ? ORDER BY claim_id",
            (post_id,))],
        "slides": [
            {"position": s["position"], "template": s["template"],
             "words": len(s["body"].split()), "png": png,
             "body": s["body"]}
            for s, png in shots
        ],
    }
    (final / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    for html in final.glob("*.html"):
        html.unlink()
    return manifest


def shoot(pages, tokens, staging: Path) -> list[tuple[sqlite3.Row, str]]:
    """Screenshot every slide. Any overflow fails the whole post."""
    from playwright.sync_api import sync_playwright

    width = tokens["canvas"]["width"]
    height = tokens["canvas"]["height"]
    shots, overflows = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--force-color-profile=srgb",
                                           "--font-render-hinting=none"])
        page = browser.new_page(viewport={"width": width, "height": height},
                                device_scale_factor=1)
        for slide, html in pages:
            page.goto(html.resolve().as_uri())
            page.wait_for_timeout(120)
            over = page.evaluate("""() => {
                const out = [];
                for (const el of document.querySelectorAll('#measure, #measure-title, .box')) {
                    const dy = el.scrollHeight - el.clientHeight;
                    const dx = el.scrollWidth - el.clientWidth;
                    if (dy > 1 || dx > 1) out.push({el: el.id || el.className, dy, dx});
                }
                const b = document.querySelector('.box');
                if (b) {
                    const r = b.getBoundingClientRect();
                    if (r.top < 0) out.push({el: 'box-top', dy: Math.round(-r.top), dx: 0});
                }
                return out;
            }""")
            if over:
                overflows.append((slide["position"], over))
                continue
            name = f'{slide["position"]:02d}.png'
            page.screenshot(path=str(staging / name))
            shots.append((slide, name))
        browser.close()

    if overflows:
        for position, over in overflows:
            detail = ", ".join(f'{o["el"]} +{o["dy"]}px' for o in over)
            print(f"OVERFLOW slide {position}: {detail}", file=sys.stderr)
        raise SystemExit("render failed: text does not fit. Shorten it in the "
                         "database. The renderer will not shrink type.")
    return shots


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="render a post to PNGs")
    ap.add_argument("--post")
    ap.add_argument("--all-ready", action="store_true")
    ap.add_argument("--db", default=str(ROOT / "claims.db"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--screen", default="duotone", choices=("duotone", "halftone"))
    ap.add_argument("--skip-lint", action="store_true",
                    help="scratch work only. Never use on claims.db.")
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
    if not ids:
        print("nothing to render")
        return 0

    for post_id in ids:
        if not a.skip_lint:
            lint = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "lint_post.py"),
                 "--post", post_id, "--db", a.db],
                cwd=str(ROOT))
            if lint.returncode != 0:
                print(f"{post_id}: linters failed, nothing rendered", file=sys.stderr)
                return 1
        manifest = render_post(conn, post_id, a.screen, Path(a.out))
        print(f'{post_id}: {len(manifest["slides"])} slides -> '
              f'{Path(a.out) / post_id}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
