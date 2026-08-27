"""Render the sample set into out/samples/ and write out/SAMPLES.md.

    python tools/build_samples.py

Fifteen carousels across the six pillars, both cover passes, the whole ink
set, mourning and normal. They exist so a human can judge design and voice
before any of this touches claims.db.

Everything here runs against scratch.db and renders with --skip-lint, because
every sample still carries [[NEEDS CLAIM: placeholders and no verified claim
rows. That flag is the reason this is a separate tool: the real pipeline in
render/render.py cannot be talked into it, and the samples cannot be mistaken
for output that passed the gates.

SAMPLES.md records, per sample, what it is testing and what the prose linter
says about it, so the linter's own judgement is part of the review.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRATCH = ROOT / "scratch.db"
OUT = ROOT / "out" / "samples"

# id -> (cover pass, what this one is for)
SAMPLES = {
    "sample-01-quraysh": ("duotone",
        "collision / rust / stone duotone. The default look of the account."),
    "sample-02-shawwal": ("duotone",
        "date_pair / iron / tilework duotone. Two dates, one of them soft."),
    "sample-03-basra": ("duotone",
        "collision / indigo / SOLID cover. Tests the inverted title block."),
    "sample-04-zabala": ("halftone",
        "map / indigo / stone HALFTONE. The screened cover pass."),
    "sample-05-thirty-seven": ("duotone",
        "number / olive / solid. A number card: arithmetic and two dates."),
    "sample-06-rajab": ("duotone",
        "calendar / MOURNING. Solid cover, night ground, bone ink, no ornament."),
    "sample-07-testimony": ("duotone",
        "collision / rust / tilework duotone. A dispute note forces the "
        "linter's name-both-accounts rule."),
    "sample-08-shroud": ("duotone",
        "fact_panel / iron / manuscript folio duotone. Quiet cover, long read."),
    "sample-09-waqifa": ("halftone",
        "collision / rust / tilework HALFTONE. The closing the whole first "
        "essay was built toward."),
    "sample-10-hamida": ("duotone",
        "fact_panel / olive / textile duotone. Tests the palette's warm end."),
    "sample-11-designation": ("duotone",
        "fact_panel / iron / carved panel duotone. Seven names on one slide."),
    "sample-12-receipts": ("duotone",
        "collision / olive / interior duotone. A cover with deep shadow."),
    "sample-13-fifty-five": ("duotone",
        "number / indigo / solid. The second number card, for comparison."),
    "sample-14-silence": ("duotone",
        "collision / MOURNING. The second mourning post, non-calendar."),
    "sample-15-names": ("halftone",
        "fact_panel / olive / tilework HALFTONE. Third screened cover."),
}


def run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, *args], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not SCRATCH.exists():
        print("no scratch.db. Run: python tools/load_essay.py "
              '"essays/samples/*.yaml" --db scratch.db', file=sys.stderr)
        return 1

    rows = []
    for post_id, (screen, purpose) in SAMPLES.items():
        code, output = run(["render/render.py", "--post", post_id,
                            "--db", str(SCRATCH), "--skip-lint",
                            "--out", str(OUT), "--screen", screen])
        ok = code == 0
        _, lint = run(["tools/lint_prose.py", "--post", post_id,
                       "--db", str(SCRATCH), "--report"])
        fails = [ln for ln in lint.splitlines() if ln.startswith("FAIL")]
        placeholders = [ln for ln in fails if "needs-claim" in ln]
        other = [ln for ln in fails if "needs-claim" not in ln]
        manifest = OUT / post_id / "manifest.json"
        slides = 0
        if manifest.exists():
            slides = len(json.loads(manifest.read_text(encoding="utf-8"))["slides"])
        rows.append({"id": post_id, "ok": ok, "screen": screen,
                     "purpose": purpose, "slides": slides,
                     "placeholders": len(placeholders), "other": other,
                     "output": output.strip()})
        print(f'{post_id:<24} {"ok" if ok else "FAILED":<7} {slides:>3} slides  '
              f'{len(placeholders):>2} placeholders  {len(other)} other findings')

    lines = [
        "# Fifteen samples",
        "",
        "Rendered from `scratch.db` by `python tools/build_samples.py`. PNGs are",
        "in `out/samples/<id>/`, one manifest each.",
        "",
        "These are NOT publishable posts. Every one of them still carries",
        "`[[NEEDS CLAIM:` placeholders and no verified claim row, so the real",
        "pipeline refuses them; the sample runner passes `--skip-lint` on",
        "purpose. What they are for is judging four things before any of this",
        "reaches claims.db: the typography, the cover system, the voice, and",
        "whether the prose rules produce prose worth reading.",
        "",
        "The `other findings` column is the prose linter running with",
        "placeholders excluded. Zero means the sample satisfies every writing",
        "rule in Phase 5.",
        "",
        "| sample | slides | cover pass | placeholders | other findings |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f'| `{r["id"]}` | {r["slides"]} | {r["screen"]} | '
                     f'{r["placeholders"]} | {len(r["other"])} |')
    lines += ["", "## What each one is testing", ""]
    for r in rows:
        lines.append(f'**{r["id"]}** - {r["purpose"]}')
        if not r["ok"]:
            lines.append(f'\n  RENDER FAILED:\n\n```\n{r["output"][:900]}\n```')
        for finding in r["other"]:
            lines.append(f'\n  linter: {finding}')
        lines.append("")
    lines += [
        "## How to read them on a phone",
        "",
        "```",
        "python tools/build_index.py        # after rendering into out/",
        "python -m http.server -d site 8000",
        "```",
        "",
        "The site reads `site/index.json`. In production the same file is built",
        "by the Action and deployed to Pages behind Cloudflare Access.",
        "",
    ]
    (ROOT / "out" / "SAMPLES.md").write_text("\n".join(lines), encoding="utf-8")
    failed = [r for r in rows if not r["ok"]]
    print(f'\n{len(rows) - len(failed)}/{len(rows)} rendered -> {OUT}')
    print(f'wrote {ROOT / "out" / "SAMPLES.md"}')
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
