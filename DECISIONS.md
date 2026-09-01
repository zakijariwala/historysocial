# Decisions

Every choice made while building this, with the reasoning. Written as the work
happened, unattended, with no chance to ask. Where a decision could have gone
either way, the simpler option won and the reason is stated.

---

## 1. A separate git repository at HISTORY-SOCIAL, not a subdirectory of `noor post`

`D:\noor post` is a git repository, and HISTORY-SOCIAL sits inside it as an
untracked directory. Committing this project there would put the render
workflow at `HISTORY-SOCIAL/.github/workflows/render.yml`, and GitHub only runs
workflows from `.github/workflows/` at the root of a repository. Phase 7 is the
point of the build, so the repository root has to be here.

`git init` in HISTORY-SOCIAL. The parent still shows the directory as
untracked, and nothing in the parent was modified.

## 2. Sources were already on the shelf, and they are not all openly licensed

The brief describes fetching from OpenITI and pre-1929 archive.org. The
`sources/` directory already held 21 PDFs, several of them modern in-copyright
translations (the SUNY al-Tabari volumes, Guillaume's Ibn Ishaq, the Ansariyan
translations). The operator states these were obtained legally or with
permission.

Both things are handled separately:

- `tools/fetch_sources.py` obeys the brief exactly. It downloads from OpenITI
  and from archive.org, refuses any archive.org item dated 1929 or later by
  re-reading the item's own metadata, and has no flag that turns either rule
  off. It prints the in-copyright titles the operator must supply by hand.
- The volumes already present are registered in `sources/manifest.yaml` with
  `licence: user-supplied` and a note that the in-copyright ones stay local.
  `sources/` is gitignored; nothing from it is committed or deployed.

## 3. Editions were left as TODO on purpose, and that blocks verification

Nothing in the manifest guesses a translator, a publisher or an ISBN. A wrong
edition statement turns every claim citing it into a false citation, and a
model's memory is exactly the wrong instrument for a bibliographic fact.

`tools/db.py verify` refuses to mark a claim verified while its source's
`edition:` still starts with TODO. That makes filling in the manifest the first
job on waking, and it makes the refusal loud instead of silent.

The one exception is SRC-TAB-AR, the OpenITI al-Tabari: that file states its
own publisher in its `#META#` header, so the edition line records what the file
says and where it says it.

## 4. Printed page numbers are reconciled against their neighbours, never trusted alone

`tools/extract_pages.py` reads a numeral from the top or bottom of each page.
On its own that is unsafe: a footnote marker at the foot of a page reads as a
page number and lands hundreds of pages away. So a numeral is only trusted when
the pages around it agree with its offset. Pages that disagree are given the
offset their neighbours support and marked `derived`; pages with nothing
readable are marked `none` and lookup prints `p. ?`.

A hit on a `p. ?` page can be read, and since decision 21 it can still become
a verified claim, provided the row carries some other locator the reader can
follow. What it can never do is claim a page number the extractor never read.

## 5. The page index speaks bytes, and the searcher folds diacritics

Two bugs, both found by running the tool rather than by reading it:

- Offsets were characters and ripgrep reports bytes. Any hit past the first
  non-ASCII character in a file landed on the wrong page. The index now stores
  byte offsets.
- Howard's Irshad prints Mūsā and Hārūn. A query for `Musa` found nothing.
  `sourcelib.fold_preserving` folds diacritics one character to one character,
  so the text can be searched folded while every offset still points into the
  original.

## 6. The spelling-family regex was too loose, and a loose search is worse than none

The first version inserted an optional vowel between every letter. A search for
`Sindi` matched `Sending`. That is the failure mode that matters most in this
project: a hit that looks like evidence and cites a page saying nothing of the
kind. The pattern is now anchored at both ends and inserts no vowels;
`al-Kazim` and `al-Kadhim` still meet, and `Sindi` no longer reaches `Sending`.

## 7. ripgrep is optional

There is no ripgrep binary on this machine, only a shell alias. `lookup.py`
uses a real `rg` when one exists and an exact query is asked for, and runs the
same regex in Python otherwise. The Python path is the one that can fold the
haystack, so the expanded search always takes it. Slower, never wrong, and CI
does not have to install anything.

## 8. Cover images: Met Open Access only, and a human looks at every one

`tools/fetch_images.py` collects from the Metropolitan Museum's open access
API, which needs no key and exposes `isPublicDomain` per object. Rijksmuseum
needs an API key, and the Biodiversity Heritage Library, Wellcome and David
Rumsey need a per-item licence check that cannot be automated safely. Those are
left for manual addition, and the tool says so.

Rule 3 gets two passes:

1. A filter over the museum record: any human term in a tag, title, object name
   or classification rejects the candidate. Rejections are written to
   `images/rejected.yaml` with reasons, so the filter can be audited.
2. A human pass. The filter accepted an Egyptian Book of the Dead (catalogued
   as a papyrus, with figure vignettes along the top register), a tomb chapel
   full of carved reliefs, and two Nigerian door boards with faces carved into
   them. Metadata lies by omission. `images/review.yaml` records the eye pass
   and `tools/apply_review.py` writes it into the bank, deleting the files of
   anything rejected so a typo cannot reach them.

`tools/lint_post.py` fails any post whose cover is still `review: pending`. A
machine's judgement about Rule 3 never reaches a published slide.

## 9. Solid covers invert instead of showing a white box

A white title box over a duotoned photograph is a hole cut in the picture, and
it works. The same white box on a paper ground disappears. Solid covers now
fill the box with the post's ink and set the title in the ground colour. Same
object, opposite polarity, and both read as the same account.

## 10. Overflow is measured on the one element that has a fixed box

The renderer compares `scrollHeight` against `clientHeight` on `#measure`, with
two pixels of tolerance, because a serif at tight leading reports a pixel or
two of ink spill on any element and that is not a layout failure. The cover
fails differently: a title too long for its box pushes the box off the top of
the canvas, so the box's rectangle is checked against the viewport instead.

Text never shrinks to fit. A slide that overflows was written too long, and the
fix belongs in the database.

## 11. Body slides are centred in the measure

Top-aligned body text left a third of the slide empty at the foot, which reads
as an unfinished slide rather than as a designed margin. Body size went from 46
to 50 px at the same time.

## 12. The essay is written into a YAML file, not typed into the CLI

`tools/load_essay.py` loads a post, its slides and its candidate claim rows
from one file, and reloading is idempotent. Editing prose and re-running the
linter is the working loop, and the loop has to be fast or the rules do not get
obeyed. The CLI in `tools/db.py` still does everything, one row at a time, for
the cases where that is what you want.

## 13. Candidate claim rows are written for the operator, unverified

Every claim row in `essays/` names a source and a printed page that a search of
the local corpus actually returned. None of them is verified and no tool can
verify them. This is the line the brief draws, and it is worth being precise
about which side of it this work sits on: locating a passage is not the same as
vouching for it. Verifying means a person opens the book at the page and reads
the sentence. What the machine did was save that person the search.

## 14. The prose linter emits FAIL and WARN, and says which rules it can only approximate

Some rules are mechanical: no em dashes, no adverbs, 60 to 100 words, slide 2
is a question. Those are FAIL. Others can only be approximated: whether a slide
depends on the one before it is judged by shared vocabulary, and passive voice
is caught by a pattern that has false positives. Those are WARN, and the
message says what a human should check.

The one structural rule the brief states as a test, that slide 4 should not
survive the removal of slide 1, is implemented directly and fails the build.

## 15. Fifteen samples live in `scratch.db` and render with `--skip-lint`

The samples carry placeholders and no verified rows, so the real pipeline
refuses them. `tools/build_samples.py` is a separate tool that passes
`--skip-lint`, and `out/SAMPLES.md` records the linter's own findings for each
sample so the reviewer sees what the gates would have said. The main renderer
has no path to this behaviour: `--skip-lint` on `claims.db` is documented as
wrong and nothing in the workflow uses it.

## 16. The mourning calendar advises and never decides

`tools/mourning.py` converts by the tabular Islamic calendar. Sistani's
calendar is set by sighting and can differ by a day. Near a boundary the tool
says so and tells the operator to check. `tokens/mourning.yaml` holds the wafat
dates as TODO entries, and the tool reports how many are unfilled every time it
runs, so an empty list can never be mistaken for a complete one.

## 17. No D1, no Worker, no R2, no scheduler, no analytics

As instructed. One SQLite file committed to the repository, one static origin
behind one Cloudflare Access policy. Shares are tracked as a column and updated
by hand with `tools/db.py metrics`, which is the whole of the analytics story.

## 18. The caption is loaded with `index.json`, not fetched on tap

iOS Safari honours `navigator.clipboard.writeText` only when it is called
synchronously inside the tap handler. Any await before the call and Safari
refuses without throwing. The caption is therefore written into `index.json` in
full, held on the button as a string, and copied with nothing between the tap
and the write.

## 19. The spelling-family regex silently dropped every word containing an `e`

Found while writing the second batch of samples, by searching for `tongue` in a
corpus that contains the word hundreds of times and getting no hits at all.

`norm()` folds `e` to `i`, and decision 6 had removed `e` from the i-class to
stop `Sindi` matching `Sending`. The two changes together meant that any query
whose normal form contained an `i` derived from a printed `e` could never match
its own source text. `Hunayf`, `tongue`, `Sending`: all silent failures, and a
silent failure in a search tool is the worst kind, because the user concludes
the corpus does not contain the thing.

`e` is back in the i-class. What actually stops `Sindi` reaching `Sending` is
the word-boundary anchors, which were added at the same time and are doing the
work on their own.

The general lesson is in the sample set: widening the range of what you test
is how you find the bug that narrow testing hides. The first fifteen samples
were all drawn from one cluster of material and never asked the searcher a
question it could fail this way.

## 20. Iron ink covers come out greyscale, and that is a design decision to make

The duotone maps a cover image between the post's ink and the ground. For
rust, indigo and olive that produces an obvious tint. For iron, which is
#191B20, the two ends are near-black and near-paper, so the cover reads as an
ordinary black and white photograph with none of the account's colour identity
on it.

Left as it is, on purpose, because it is a legitimate look and the choice
belongs to the operator rather than to me. Three options, in order of how much
they change:

  1. Accept it. Iron becomes the account's black and white cover, used
     deliberately for the posts that should feel documentary.
  2. Lift the highlight for iron only, mapping to sand rather than paper, which
     warms the whole image without touching the other four inks.
  3. Drop iron from cover use and keep it for interior slides, where near-black
     on paper is exactly right.

sample-19 and sample-28 are the two iron covers in the sample set. Compare
them with sample-01 (rust) and sample-24 (indigo) to judge.

## 21. The page rule became a locator rule

Rule 2 used to read: no printed page number, no verified claim. It has been
replaced by: no locator, no verified claim, where a locator is whatever
addresses the passage in the edition named on the row.

The old rule assumed every source is a printing. Most of this shelf is not.
Fourteen of the twenty-six registered sources are `pagination:
ebook-reflowed` — al-islam.org, alhassanain and Ansariyan conversions whose
page numbers were set by the conversion, not by a typesetter. SRC-QAR-001's
own manifest note said so from the start. The same translation reflows
differently at each of those three sites, and different countries reprint the
same title at different pagination, so "p. 407" identifies a passage only for
the person holding the identical file.

Worse, `verification_block()` never checked `pagination`. A reflowed ebook page
verified clean, which meant the rule the whole project exists to enforce was
being satisfied by numbers that exist in no book. A rule that cannot be
satisfied honestly gets satisfied dishonestly.

`claim.page` is therefore `claim.locator`, free text, still required before a
row can be verified. What goes in it is the unit the edition actually carries:

    bk. 2, ch. 4, hadith 12      al-Kafi, any printing
    sermon 27                    Nahj al-Balagha, any printing
    Leiden 8:271                 al-Tabari, the margin numbers every
                                 translation and the Arabic both carry
    p. 407                       still correct where the edition is a printing

The three `pagination: print-edition` sources — SRC-TAB-008, SRC-TAB-040 and
SRC-SIR-001 — lose nothing: a page in a real printing is a good locator and
stays one.

What this trades away is machine-checkability. A page number could at least be
compared against the extracted page index; free text cannot be checked by
anything but a reader. The gate now enforces that a locator exists and that the
edition it points into is named, and nothing more. Rule 1 is unchanged: a human
still has to open the book.

The twelve verified rows on `musa-bridge` carried real printed pages from
Howard's Irshad and al-Kafi. They were carried over as locators unchanged,
normalised to `p. 407` form, and stay verified. Nothing already approved had to
be approved twice.

## 22. The tradition and hostile-witness rule

The README opened with "openly Shia", but until migration 0005 that was an
editorial stance with no gate enforcing it. `sources/manifest.yaml` modelled no
traditions, and `verification_block()` checked only formal bibliographic
presence: registration, edition statement, locator, index-only flag, and
usability. A claim resting entirely on a Sunni chronicle verified identically to
one resting on al-Kafi.

The account is openly Shia. Citing a Sunni chronicle down a chain of
transmission is borrowing authority from a tradition this account does not hold
authoritative. Citing that same chronicle for what its annalistic record does—what
it enters, omits, concedes, or files under a year—is treating the source as a
hostile witness. The hostile witness who records a death without mentioning
poison is evidence precisely because he is hostile.

The distinction is between **borrowed authority** and **record observation**:

- **Borrowed authority (refused):** Content carried down a transmission chain
  (e.g., "reports on the authority of 'Amra that 'A'isha said..."). This borrows
  authority from a non-Shia chain.
- **Bare fact (refused):** A free-standing historical claim resting only on a
  non-Shia source (e.g., "alongside the Ka'ba the Arabs had adopted tawaghit...").
- **Record observation (allowed as hostile witness):** An assertion about what
  the opposing record itself enters, omits, or juxtaposes (e.g., "the Arabic
  chronicle records the death at Baghdad in the same year as that of Muhammad b.
  al-Sammak the qadi").

Every source in `sources/manifest.yaml` is now tagged `tradition: shia|sunni`.
A claim citing a non-Shia source verifies only when explicitly declared with
`--role hostile-witness`. The code (`db.hostile_witness_block()`) scans for
`CHAIN_MARKERS` and `RECORD_MARKERS`. These markers are **tripwires, not
proofs**: natural language can disguise borrowed authority, so `--role
hostile-witness` is a human attestation and the machine checks only catch
obvious transmission patterns. Furthermore, `lint_post.py` enforces that a
hostile witness cannot stand alone: a post must carry verified Shia claims for
the hostile witness to be argued against.

Under this rule, `sample-19-two-stones` was retired. Its entire thesis was Ibn
Ishaq's qualification of an 'A'isha narration. Because no Shia source carries
the narration, and because the essay's core argument *was* the narration, the
post could not survive without borrowing non-Shia authority and was dropped
rather than rewritten.

