-- 0001_initial: the whole schema.
--
-- Repeatable. Every statement is IF NOT EXISTS, so running the migration
-- twice is a no-op rather than an error.
--
-- The claim table is the spine of the project. A slide renders only from rows
-- here that carry verified = 1, and a row cannot reach verified = 1 without a
-- printed page. Everything else in the repository is presentation.

CREATE TABLE IF NOT EXISTS claim (
  id            TEXT PRIMARY KEY,
  subject       TEXT NOT NULL,
  assertion     TEXT NOT NULL,
  hijri_date    TEXT,
  ce_date       TEXT,
  source_key    TEXT NOT NULL,          -- a key in sources/manifest.yaml
  edition       TEXT NOT NULL,          -- the edition statement, spelled out
  page          TEXT,                   -- printed page. NULL cannot be verified.
  verified      INTEGER DEFAULT 0,
  verified_by   TEXT,
  verified_on   TEXT,
  dispute_note  TEXT,                   -- where the chronicles disagree, both
  pillar        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS post (
  id            TEXT PRIMARY KEY,
  pillar        TEXT NOT NULL,          -- collision|fact_panel|map|calendar|number|date_pair
  running_head  TEXT NOT NULL,          -- appears on every interior slide
  cover_title   TEXT NOT NULL,          -- lowercase, under 8 words
  cover_image   TEXT,                   -- an id in images/bank.yaml; NULL = solid
  ink           TEXT NOT NULL,          -- a key in tokens/tokens.yaml inks
  caption       TEXT NOT NULL,
  mourning      INTEGER DEFAULT 0,
  status        TEXT DEFAULT 'draft',   -- draft|ready|posted
  shares        INTEGER,
  likes         INTEGER,
  saves         INTEGER
);

CREATE TABLE IF NOT EXISTS slide (
  post_id       TEXT NOT NULL,
  position      INTEGER NOT NULL,
  template      TEXT NOT NULL,          -- cover|question|body|closing
  body          TEXT NOT NULL,
  PRIMARY KEY (post_id, position)
);

CREATE TABLE IF NOT EXISTS post_claim (
  post_id       TEXT NOT NULL,
  claim_id      TEXT NOT NULL,
  PRIMARY KEY (post_id, claim_id)
);

CREATE INDEX IF NOT EXISTS claim_pillar_idx   ON claim (pillar);
CREATE INDEX IF NOT EXISTS claim_verified_idx ON claim (verified);
CREATE INDEX IF NOT EXISTS claim_subject_idx  ON claim (subject);
CREATE INDEX IF NOT EXISTS post_status_idx    ON post (status);

-- Which migrations have run. Written by tools/db.py migrate.
CREATE TABLE IF NOT EXISTS schema_migration (
  filename   TEXT PRIMARY KEY,
  applied_on TEXT NOT NULL
);
