-- 0003_posted_on: the durable record of what actually went out.
--
-- The review site carries per-browser tick boxes in localStorage. They are
-- advisory and lossy by design: they do not follow the account to a second
-- device and clearing site data clears them. `posted_on` is the signal that
-- survives, and a post counts as posted if this column is set OR the local
-- tick is on. See site/ §4.
--
-- NULL means not posted. Set it with: tools/db.py status <post> posted

ALTER TABLE post ADD COLUMN posted_on TEXT;
