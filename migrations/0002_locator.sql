-- 0002_locator: a claim is pinned by a locator, not by a page number.
--
-- The page rule assumed one printing. It does not survive contact with the
-- shelf: Ansariyan, alhassanain and al-islam.org reflow the same translation
-- to different pagination, and fourteen of the registered sources are ebook
-- conversions whose page numbers exist in no printed book at all. A rule that
-- cannot be satisfied honestly gets satisfied dishonestly.
--
-- `locator` is free text and carries whatever unit is actually stable for the
-- source in hand: a chapter, a book and hadith number, a sermon, a Leiden
-- margin number, a folio. A printed page is still a perfectly good locator
-- where the edition is a real printing. What the gate now requires is that
-- SOMETHING addresses the passage, and that the edition it addresses is named.
--
-- NOT repeatable: RENAME COLUMN fails on second run. tools/db.py migrate now
-- applies only the files it has not already recorded.

ALTER TABLE claim RENAME COLUMN page TO locator;
