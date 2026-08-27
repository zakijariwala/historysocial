# Blocked

Things that could not be done, why, and what would unblock them. Nothing here
stopped the rest of the build.

---

## 1. Two source PDFs are encrypted and cannot be opened

```
worldhistory--timetablesofhist0000grun-h6t8.pdf
worldhistory--timetablesofhist00grun-0.pdf
```

`PDFium: Unsupported security scheme error`. Both are Grun's *Timetables of
History*, both refuse to open for text extraction.

**Unblock:** open each in a reader that accepts them and re-save without
encryption, then run `python tools/extract_pages.py`. They are a world-history
reference rather than a source for any claim about the Imams, so nothing in
Phase 8 waits on them.

## 2. One Guillaume scan has no text layer

`sira-guillaume--thelifeofmohammedguillaume.pdf` is 432 pages and yields 431
characters. It is page images with no OCR.

**Unblock:** nothing needs doing. `sira-guillaume--guillaumeathelifeofmuhammad.pdf`
carries the same translation with a usable text layer and is registered as
SRC-SIR-001. The scan is registered as SRC-SIR-002 with `usable: false`.

## 3. The public-domain Arabic editions came back as broken OCR

`tools/fetch_sources.py` successfully downloaded four public-domain texts from
archive.org:

```
degoeje--tabari-annales-01.txt    de Goeje, Leiden 1879
degoeje--tabari-annales-02.txt    de Goeje, Leiden 1890
wustenfeld--yaqut-mujam-01.txt    Wustenfeld, Leipzig 1866
wustenfeld--yaqut-mujam-02.txt    Wustenfeld, Leipzig 1867
```

All four are Arabic type OCRed as Latin noise. They cannot be searched and
nothing in them can be cited. They are registered with `usable: false`.

This matters most for Yaqut: distances between towns have no source on this
shelf, which is why every distance in the essays is a placeholder.

**Unblock, in order of effort:**

1. Use the OpenITI al-Tabari that did come through clean (SRC-TAB-AR, 6,438
   pages, page markers intact). It covers the chronicle but not the geography.
2. Find an OpenITI or Shamela edition of Yaqut and add it to the catalogue in
   `tools/fetch_sources.py`. The tool already resolves an OpenITI directory
   listing, so a new entry is three lines.
3. Run the archive.org scans through Arabic OCR locally (tesseract with
   `ara`). Slow, and the result still needs checking against the page images.

## 4. OpenITI has no al-Mufid Irshad at the path tried

`data/0413Mufid` returns 404 in both `0425AH` and `0450AH`. The Arabic behind
Howard's translation would let a reader check the English against the original.

**Unblock:** find the correct OpenITI author and book directory, then add a
catalogue entry. The Howard translation itself (SRC-IRS-003) is on hand and
complete, so nothing is blocked on this.

## 5. The cover bank has no botanical plates, maps or empty ground

The Met searches for those subjects returned either nothing public-domain or
objects outside the permitted subject list. Two late searches also failed with
a DNS error mid-run. The bank ended at eleven approved images: tilework, stone,
textile, one manuscript folio, one carved panel.

**Unblock:** `python tools/fetch_images.py --collect --append` re-runs and keeps
existing approvals. For the missing subjects, the Biodiversity Heritage Library
(botanical plates) and David Rumsey (maps) are the right sources, and both need
a per-item licence check that this pipeline deliberately does not automate. Add
them by hand to `images/bank.yaml` with the licence recorded, then review them
in `images/review.yaml`.

## 6. Nothing has been deployed

No Cloudflare account, API token, account ID or Pages project is available in
this environment, and creating one is an outward-facing action nobody was awake
to approve. The workflow, the site and the build are complete and untested
against a live Pages project.

**Unblock:** DEPLOYMENT.md, top to bottom. It is about fifteen minutes.

## 7. The Actions workflow has never run

Same reason. It is written against `ubuntu-latest`, installs Chromium through
Playwright and the bundled fonts from `fonts/`, and fails the job if
`fc-list` cannot see them after install. The render, the linters, the index
build and the sample renders have all been run locally on Windows, which is
where the real risk lies: Chromium on Linux may hyphenate or wrap a line
differently.

**Unblock:** push, watch the first run, and compare one rendered slide against
the local PNG of the same slide.
