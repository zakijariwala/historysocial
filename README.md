# history-social

A deterministic pipeline for long-form essay carousels: 12 to 20 slides, one
anchor a week plus two singles, openly Shia, sourced to a named edition.

Claims live in SQLite. Slides render locally to 1080x1350 PNGs, deployed to
Cloudflare Pages for mobile review behind Cloudflare Access.

---

## The rule the whole thing exists to enforce

**A slide renders only from claim rows marked verified, and a row cannot be
marked verified without a named edition and a locator inside it.**

Everything else is machinery around that. Where an essay needs a fact with no
verified row behind it, the sentence carries a visible placeholder:

```
[[NEEDS CLAIM: the date and the age at death, Irshad p. 407]]
```

A placeholder is correct output. An invented fact is a build failure. The
linter fails any render containing one, so drafts stay in the database and
never reach a PNG.

## First five minutes

```bash
pip install -r requirements.txt
python -m playwright install chromium

python tools/extract_pages.py               # PDFs -> page-preserving text
python tools/lookup.py "Musa b. Ja'far"     # search, by PRINTED page
python tools/db.py coverage                 # what is verified, per pillar
python tools/lint_post.py --post musa-bridge --report
```

## The loop

```
1. read           tools/lookup.py "al-Sindi" --source irshad-howard --context 1
2. record         tools/db.py claim-add ... --source SRC-IRS-003 --locator "p. 407"
3. verify         tools/db.py verify CLM-0001 --by zaki       ← a human, always
4. write          edit essays/<post>.yaml
5. load           tools/load_essay.py essays/<post>.yaml
6. lint           tools/lint_post.py --post <post> --report
7. mark ready     tools/db.py status <post> ready
8. render & site  python render/render.py --all-ready && python tools/build_site.py
9. deploy         npx wrangler pages deploy site --project-name=history-social
10. review        on the phone: swipe, DOWNLOAD ALL, COPY CAPTION
```

Step 3 is the only step a machine cannot do.

## Layout

```
sources/          gitignored except manifest.yaml. PDFs, extracted text, page index
images/           bank.yaml + bank/*.jpg, committed. review.yaml records the eye pass
fonts/            EB Garamond + Space Grotesk, OFL, committed and installed from here
claims.db         SQLite, committed. The truth
migrations/       0001_initial.sql onward, repeatable
essays/           the writing surface. One YAML file per post
  samples/        fifteen samples for judging design and voice
templates/        cover, question, body, closing. Four, and that is the system
tokens/           five inks, four grounds, the type scale, the mourning pair
render/           render.py, duotone.py
tools/            everything else, one job each
site/             the phone app. Static review UI reading data/index.json
out/              gitignored. PNGs and manifests
```

## The tools

| tool | what it does |
|---|---|
| `fetch_sources.py` | downloads from OpenITI and pre-1929 archive.org only, and prints the in-copyright list you must supply by hand |
| `extract_pages.py` | PDF to text with a byte-offset page index; page numbers reconciled against their neighbours |
| `ingest_text.py` | the same index for plain-text sources (OpenITI page markers) |
| `lookup.py` | search, returning PRINTED page numbers; finds Ja'far, Jafar and Jaʿfar with one query |
| `db.py` | add, verify, list, coverage, posts, slides, metrics |
| `load_essay.py` | load an essay YAML into the database, idempotently |
| `lint_prose.py` | the Phase 5 writing rules |
| `lint_post.py` | the render gates: verified claims, placeholders, licences, mourning tokens |
| `fetch_images.py` | collect cover images with licences and a human-figure filter |
| `apply_review.py` | write the human review into the bank; delete what was rejected |
| `mourning.py` | is today inside the mourning window (advises, never decides) |
| `needs_claims.py` | regenerate NEEDS_CLAIMS.md from the placeholders in the database |
| `build_site.py` | site/data/index.json, zips, PNG copies for mobile review |
| `build_samples.py` | render the fifteen samples into out/samples/ |


## Four templates, two typefaces, five inks

```
cover     image (duotone or halftone) or solid ground
          title box, grotesque, justified, lowercase, fixed sub-line beneath
question  solid ground, serif, the largest type in the system. ALWAYS slide 2
body      solid ground, serif, 60 to 100 words, tight leading
closing   solid ground, the line the essay was built for
```

The running head, the essay title in small italic serif, sits top-left on every
interior slide. It brands any single slide somebody screenshots. It is never
omitted, and the linter enforces that.

Mourning runs Muharram 1 to Safar 30 plus the wafat dates: solid cover, night
ground, bone ink, no ornament.

## Rules that have no override flag

1. A slide renders only from verified claim rows.
2. Every verified claim carries source, edition and locator.
3. **No human figures in any image, ever.** Enforced twice: a filter over the
   museum record, then a person looking at the pixels. `images/review.yaml`
   records who looked.
4. Two typefaces, five inks, fonts bundled and never fetched at render time.
5. Rendered PNGs are never committed.

## Where to look next

- **DECISIONS.md** every choice made in this build, with reasoning
- **ARCHITECTURE.md** why SQLite, why no Worker, and when R2 becomes worth it
- **DEPLOYMENT.md** the token permissions, the Access policy, the first run
- **NEEDS_CLAIMS.md** every placeholder, grouped by the source that would settle it
- **BLOCKED.md** what could not be done and what would unblock it
- **TASKS.md** the phase-by-phase state of the build
- **out/SAMPLES.md** the fifteen samples and what each one tests
