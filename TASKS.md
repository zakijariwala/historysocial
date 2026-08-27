# Task list

Kept current as the build runs. `[x]` done, `[~]` in progress, `[ ]` pending,
`[!]` blocked (see BLOCKED.md).

## Phase 0 - repository

- [x] Own git repository at HISTORY-SOCIAL (the parent `noor post` repo cannot
      run this project's Actions workflow; see DECISIONS.md)
- [x] `.gitignore`: sources local, renders never committed, bank images kept
- [x] Two typefaces bundled: EB Garamond (serif + italic), Space Grotesk
      (grotesque), both OFL, licences committed beside them
- [x] `requirements.txt`

## Phase 1 - source layer

- [x] `tools/sourcelib.py` - transliteration normaliser, spelling-family regex
- [x] `tools/extract_pages.py` - PDF to page-preserving text, printed page
      numbers reconciled against their neighbours, byte-offset page index
- [x] `tools/ingest_text.py` - the same index for plain-text sources
      (OpenITI page markers)
- [x] `tools/lookup.py` - search returning PRINTED pages, ripgrep or Python
- [x] `tools/fetch_sources.py` - OpenITI and pre-1929 archive.org only;
      prints the in-copyright list the operator must supply
- [x] `sources/manifest.yaml` - 26 volumes registered, editions left TODO on
      purpose
- [x] All 21 local PDFs extracted; 5 open-licence texts fetched
- [!] 2 world-history PDFs are encrypted, 1 Guillaume scan has no text layer,
      4 fetched OCR files are unusable (BLOCKED.md)

## Phase 2 - database

- [x] `migrations/0001_initial.sql` - claim, post, slide, post_claim, repeatable
- [x] `tools/db.py` - add, verify, unverified, coverage, post-create, slide-set,
      link, status, drafts, metrics (shares first)
- [x] verify refuses: no page, TODO edition, index-only source, unregistered
      source

## Phase 3 - cover image bank

- [x] `tools/fetch_images.py` - Met Open Access, per-object public-domain check,
      human-figure rejection filter, rejects logged for audit
- [~] `images/bank.yaml` written by the collect run
- [x] `render/duotone.py` - duotone and halftone passes

## Phase 4 - templates and tokens

- [x] `tokens/tokens.yaml` - five inks, four grounds, two typefaces, type scale
- [x] `templates/base.html` + cover, question, body, closing
- [x] Running head on every interior slide; overflow measured, never shrunk

## Phase 5 - writing rules

- [x] `tools/lint_prose.py` - structure, sentences, evidence, register
- [ ] `tools/lint_post.py` - the render gates (verified claims, placeholders,
      licence, mourning tokens, slide 2)

## Phase 6 - renderer

- [x] `render/render.py` - Jinja2 + Playwright, 1080x1350, manifest per post
- [ ] End-to-end render proved on a real post

## Phase 7 - delivery

- [ ] `.github/workflows/render.yml`
- [ ] `site/` - TODAY, READY, ARCHIVE, swipeable viewer, iOS-safe clipboard
- [ ] `tools/build_index.py` - site/index.json, zips
- [ ] `tools/mourning.py` - Muharram 1 to Safar 30 plus the wafat dates

## Phase 8 - first essay

- [ ] Musa b. Ja'far, 16 slides, running head "the imam who spent nineteen
      years in custody", closing on the Waqifa split
- [ ] `NEEDS_CLAIMS.md` - every placeholder, grouped by the source that
      would settle it
- [ ] Three cover variants in a scratch database

## Phase 9 - fifteen samples for quality review

- [ ] Fifteen carousels across the six pillars, rendered locally from
      `scratch.db`, spanning mourning and normal, image and solid covers,
      both cover passes, and the full ink set
- [ ] `out/SAMPLES.md` - what each one is testing

## Deliverables

- [ ] ARCHITECTURE.md, DEPLOYMENT.md, README.md, DECISIONS.md,
      NEEDS_CLAIMS.md, BLOCKED.md
