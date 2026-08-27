# Architecture

One sentence: a local SQLite database of sourced claims and drafted slides,
rendered to PNGs by headless Chromium inside GitHub Actions, published as a
static site behind Cloudflare Access, reviewed on a phone.

```
sources/*.pdf ──► extract_pages.py ──► sources/text/*.txt
                                       sources/pages/*.pages.jsonl
                                              │
                                       lookup.py  (printed pages)
                                              │
                          a human reads the page and writes a row
                                              ▼
essays/*.yaml ──► load_essay.py ──►      claims.db
                                     claim · post · slide · post_claim
                                              │
                              lint_post.py + lint_prose.py   ← the gate
                                              ▼
                          render.py (Jinja2 → Chromium → PNG)
                                              │
                                       out/<post>/*.png
                                       out/<post>/manifest.json
                                              ▼
                              build_index.py → site/index.json
                                                site/posts/<post>/
                                              ▼
                          wrangler pages deploy site   (Actions)
                                              ▼
                       Cloudflare Pages + Access → an iPhone
```

## What is truth

The database and the render manifest. The PNG is output and can be deleted at
any time; running the workflow again reproduces it byte for byte from the same
rows, the same tokens and the same renderer version.

That ordering is why PNGs are gitignored, why `manifest.json` is written beside
them, and why the renderer stamps `renderer_version` into every manifest.

## Why SQLite and not D1

The database is single-writer, single-machine, a few hundred kilobytes, and it
has to be diffable in review. A committed SQLite file gives version history for
free and makes the Action's job trivial: check out the repository and the data
is already there. D1 would add a network hop, a binding, a migration story and
an account dependency to a workload with one writer.

## Why no Worker and no R2

The site is static. `index.json` plus PNGs plus one zip per post. There is
nothing to compute at request time, so there is nothing for a Worker to do.
Cloudflare Access sits in front of the whole origin and needs no auth code.

## The free tier, and what would break it

Cloudflare Pages allows 500 builds a month and 20,000 files per deployment.

One carousel is roughly 20 files: 12 to 20 PNGs, a zip, a manifest. One weekly
anchor plus two singles is about 60 files a week, so:

```
   20,000 files / 60 files per week  ≈  333 weeks  ≈  6.4 years
   500 builds a month / ~13 pushes a week  ≈  comfortable
```

Nothing in this design approaches either limit within the horizon anyone should
plan for.

## When R2 becomes worth adding

Two triggers, and neither is close:

1. **The file count.** Deployments approach 20,000 files, which on the numbers
   above means roughly six years of weekly posting with nothing ever removed.
2. **Deploy time.** Every deployment uploads the whole archive. Once that is
   thousands of files, a one-post change costs minutes of build time even
   though the new bytes are tiny.

**How to make the move, when it comes.** The change is contained because the
frontend only ever reads `index.json`:

- Create an R2 bucket and a custom domain for it, or serve it through a small
  Worker so the same Access policy covers it.
- Change `tools/build_index.py` to upload PNGs and zips to R2 and to write
  absolute URLs into `index.json` instead of the relative `posts/<id>/…` paths
  it writes now. That is the only file that needs to change.
- Keep the most recent four to six posts in `site/` so the TODAY and READY
  screens stay fast and stay inside one origin, and let ARCHIVE point at R2.
- `site/app.js` needs no change at all: it already uses whatever path
  `index.json` gives it, for both `<img src>` and the download link.
- Add `CLOUDFLARE_R2_*` credentials as Actions secrets, scoped to that bucket.

Do not do this before a trigger fires. R2 adds an egress path, a second set of
credentials and a second thing that can be misconfigured into being public.

## The source layer never leaves the machine

`sources/` is gitignored except for `manifest.yaml`. Extracted text, page
indexes and the PDFs themselves are never committed, never uploaded and never
deployed. The Action never touches them: it renders from `claims.db`, which
holds the sentences a human already approved.

This matters legally, because several volumes on the shelf are in-copyright
translations held under the operator's own licence, and it matters practically,
because it keeps the deployed artefact small.

## Determinism

- Fonts are bundled in `fonts/` and installed from the repository. Chromium in
  a runner has no serif and no Arabic face; a fetched font would fail silently
  into boxes.
- The duotone and halftone passes are pure functions of the source image and
  two colours.
- The renderer writes into a temporary directory and moves the result into
  place only when every slide of a post has succeeded, so `out/<post>/` is
  never half a carousel.
- Text overflow fails the build. Nothing is scaled to fit, so the same rows
  produce the same layout on any machine with the same fonts.

## The one thing that is not deterministic

Chromium's line breaking can differ between versions and platforms. A slide
sitting one word from the edge of its box on Windows can overflow on Linux and
fail the workflow. That is the intended failure: it fails loudly, at build
time, rather than shipping a clipped slide. The fix is to shorten the slide.
