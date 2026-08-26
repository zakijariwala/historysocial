"""Shared helpers for the source layer.

Two jobs live here:

  norm()          one normal form for transliterated Arabic, so that a single
                  query finds Ja'far, Jafar and Jaʿfar.
  variants()      the spelling family of a query term, used to build the
                  ripgrep pattern in lookup.py.

No embeddings. No vector search. Character rules only, so a match is always
explainable and always reproducible.
"""

from __future__ import annotations

import re
import unicodedata

REPO_KEYS = ("sources", "text", "pages")

# Characters that carry no distinction once transliteration is normalised.
# ayn and hamza appear as at least eight glyphs across the editions on hand.
AYN_HAMZA = "\u02bf\u02be\u2018\u2019\u02bb\u02bc\u02c0\u02c1'`\u00b4\u201b"

# Digraph and single-letter equivalences, applied after diacritic stripping.
# Order matters: longest first.
FOLD = [
    ("dh", "z"), ("th", "t"), ("kh", "k"), ("gh", "g"),
    ("sh", "s"), ("ch", "s"), ("ph", "f"),
    ("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u"),
    ("ou", "u"), ("iy", "i"), ("uw", "u"),
    ("q", "k"), ("y", "i"), ("w", "u"), ("e", "i"), ("o", "u"),
]


def strip_diacritics(s: str) -> str:
    """Drop combining marks and Arabic harakat, keep the base letters."""
    s = unicodedata.normalize("NFKD", s)
    out = []
    for ch in s:
        if unicodedata.combining(ch):
            continue
        if "\u064b" <= ch <= "\u0652":       # Arabic harakat
            continue
        out.append(ch)
    return unicodedata.normalize("NFKC", "".join(out))


def norm(s: str) -> str:
    """Aggressive normal form. Two spellings of one name collapse to one key."""
    s = strip_diacritics(s).lower()
    s = "".join(" " if ch in AYN_HAMZA else ch for ch in s)
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", "", s)
    for a, b in FOLD:
        s = s.replace(a, b)
    s = re.sub(r"(.)\1+", r"\1", s)          # collapse doubled letters
    return s


def loose_pattern(term: str) -> str:
    """A regex that matches every plausible printed spelling of `term`.

    Built letter by letter from the normalised form. Between every pair of
    letters an optional apostrophe-class character and an optional vowel are
    allowed, which is what separates Jafar from Ja'far from Jaʿfar. Consonants
    that transliterate two ways (k/q, i/y, u/w, t/th) expand to a class.
    """
    key = norm(term)
    # Real characters, not \u escapes. The same pattern string is handed to
    # Python's re and to ripgrep, and those two disagree about escape syntax.
    sep = "[" + AYN_HAMZA + "\u2010\u2011\\-]?"
    expand = {
        "k": "(?:k|q|kh|c)", "d": "(?:d|dh|z)", "t": "(?:t|th)",
        "s": "(?:s|sh|th|c)", "g": "(?:g|gh)", "f": "(?:f|ph)",
        "z": "(?:z|dh|d|th)", "i": "(?:i|y|ee|ie|e)", "u": "(?:u|w|oo|ou|o)",
        "a": "(?:a|aa|e)",
    }
    parts = []
    for ch in key:
        parts.append(expand.get(ch, re.escape(ch)))
        parts.append(sep + "[aeiou]?")
    # a final -h is optional: Kazimiyya and Kazimiyyah are one word
    return "".join(parts[:-1]) + "h?"


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)
