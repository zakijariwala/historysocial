# Task list

`[x]` done, `[ ]` pending, `[!]` blocked (see BLOCKED.md).

Phases 0 through 9 are complete. What remains is the part only you can do:
fill in the editions, verify claim rows, and deploy.

## Phase 0 - repository

- [x] Own git repository at HISTORY-SOCIAL (the parent `noor post` repo cannot
      run this project's Actions workflow; DECISIONS.md #1)
- [x] `.gitignore`: sources local, renders never committed, bank images kept
- [x] EB Garamond (serif + italic) and Space Grotesk (grotesque) bundled with
      their OFL licences
- [x] `requirements.txt`

## Phase 1 - source layer

- [x] `tools/sourcelib.py` normaliser and spelling-family regex
- [x] `tools/extract_pages.py`, printed pages reconciled against neighbours,
      byte-offset page index
- [x] `tools/ingest_text.py` for plain-text sources (OpenITI page markers)
- [x] `tools/lookup.py` returning PRINTED pages, ripgrep optional
- [x] `tools/fetch_sources.py`, OpenITI and pre-1929 archive.org only
- [x] `sources/manifest.yaml`, 26 volumes registered, editions left TODO
- [x] 21 local PDFs extracted; 5 open-licence texts fetched
- [!] 2 PDFs encrypted, 1 scan has no text layer, 4 fetched OCR files unusable

## Phase 2 - database

- [x] `migrations/0001_initial.sql`, repeatable
- [x] `tools/db.py`: claim-add, verify, unverified, coverage, post-create,
      slide-set, link, status, drafts, metrics
- [x] verify refuses on: no page, TODO edition, index-only source, unregistered
      source

## Phase 3 - cover image bank

- [x] `tools/fetch_images.py`, Met Open Access, per-object public-domain check,
      human-figure filter, rejects logged
- [x] `images/review.yaml` + `tools/apply_review.py`: a person looked at every
      image; 12 rejected on the pixels, 11 approved
- [x] `render/duotone.py`: duotone and halftone passes
- [!] no botanical plates, maps or empty ground in the bank yet

## Phase 4 - templates and tokens

- [x] `tokens/tokens.yaml`: five inks, four grounds, type scale, mourning pair
- [x] `templates/`: base, cover, question, body, closing
- [x] Running head on every interior slide; overflow measured, never shrunk
- [x] Solid covers invert to an ink block (DECISIONS.md #9)

## Phase 5 - writing rules

- [x] `tools/lint_prose.py`: structure, sentences, evidence, register
- [x] `tools/lint_post.py`: the render gates

## Phase 6 - renderer

- [x] `render/render.py`: Jinja2 + Playwright, 1080x1350, manifest per post
- [x] Proved end to end: 15 sample carousels, 196 slides, no partial output

## Phase 7 - delivery

- [x] `site/`: TODAY, READY, ARCHIVE, swipeable viewer, iOS-safe clipboard
- [x] `tools/build_site.py`: index.json, zips, PNG copies into `site/data/`
- [x] `tools/mourning.py` + `tokens/mourning.yaml`
- [x] Deployed live to Cloudflare Pages (`https://history-social.pages.dev`)
- [!] Cloudflare Access configuration pending in Zero Trust dashboard

## Phase 8 - first essay

- [x] Musa b. Ja'far, 16 slides, running head "the imam who spent nineteen
      years in custody", closing on the Waqifa split
- [x] 13 placeholders, 10 candidate claim rows with real source pages
- [x] `NEEDS_CLAIMS.md`, grouped by the source that would settle each
- [x] Three cover variants in `scratch.db`: manuscript folio duotone, tilework
      duotone, solid (`out/scratch/`)

## Phase 9 - first fifteen samples

- [x] 15 carousels across six pillars, both cover passes, five inks, two
      mourning posts, image and solid covers
- [x] Every sample passes every Phase 5 prose rule; only placeholder findings
      remain
- [x] `out/SAMPLES.md`

## Phase 10 - fifteen more samples, wider range

- [x] Sources widened past the Musa material: Risalat al-Huquq, Tuhaf al-'Uqul,
      Tabari volume VIII, Ibn Ishaq via Guillaume, Subhani, Nahj al-Balagha
      commentary, al-Qarashi on the twelfth Imam, 'Uyun Akhbar al-Rida
- [x] Slide counts at both ends: two posts at 20 (the maximum), several at 12
      (the minimum), 13 to 18 in between
- [x] Cover titles at both ends: two words, and seven, which is the limit
- [x] Three mourning posts in the set, two of them long
- [x] All eleven approved bank images used at least once across the thirty
- [x] Found and fixed a real bug in the process: the spelling-family regex
      dropped `e` from the i-class, so any query containing an `e` matched
      nothing. `tongue` returned no hits in a corpus full of tongues.

## Yours, in order

- [x] Fill `edition:` for the sources you will actually cite in
      `sources/manifest.yaml`. Until then nothing can be verified.
      Start with SRC-IRS-003 (Howard's Irshad) and SRC-KAF-001 (al-Kafi).
- [x] Verify the ten candidate rows on `musa-bridge`:
      `python tools/db.py unverified` then `verify <id> --by zaki`
- [x] Work down NEEDS_CLAIMS.md, replacing placeholders with sentences the
      page supports
- [x] Review the eleven cover images yourself in `images/bank/`; the review in
      `images/review.yaml` is mine, and Rule 3 should have your eyes on it
- [x] Fill the wafat dates in `tokens/mourning.yaml` from Sistani's calendar
- [!] Configure Cloudflare Access in Zero Trust dashboard per DEPLOYMENT.md § 3
- [x] `python tools/db.py status musa-bridge ready` when the essay is clean

