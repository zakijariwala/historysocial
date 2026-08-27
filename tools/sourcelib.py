"""Shared helpers for the source layer.

Two jobs live here:

  norm()          one normal form for transliterated Arabic, so that a single
                  query finds Ja'far, Jafar and Jaʿfar.
  loose_pattern() the spelling family of a query term, as a regex, used by
                  lookup.py.

No embeddings. No vector search. Character rules only, so a match is always
explainable by reading the pattern, and always reproducible.
"""

from __future__ import annotations

import re
import unicodedata

# Characters that carry no distinction once transliteration is normalised.
# ayn and hamza appear as at least eight glyphs across the editions on hand.
AYN_HAMZA = "ʿʾ‘’ʻʼˀˁ'`´‛"

# Digraph and single-letter equivalences, applied after diacritic stripping.
# Order matters: longest first. dh folds to z, so al-Kazim and al-Kadhim meet.
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
        if "ً" <= ch <= "ْ":       # Arabic harakat
            continue
        out.append(ch)
    return unicodedata.normalize("NFKC", "".join(out))


def fold_preserving(s: str) -> str:
    """Strip diacritics WITHOUT changing the string's length.

    Howard's Irshad prints Mūsā and Hārūn; a query for Musa has to reach them.
    Ordinary NFKD stripping would shorten the text, and every offset computed
    from it would point at the wrong page, so this folds one character to one
    character and leaves anything that will not fold alone.
    """
    out = []
    for ch in s:
        if ch in AYN_HAMZA:
            out.append("'")
            continue
        base = unicodedata.normalize("NFD", ch)[0]
        out.append(base if base.isascii() and base.isalpha() else ch)
    return "".join(out)


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
    """A regex matching every plausible printed spelling of `term`.

    Built letter by letter from the normalised form. Between every pair of
    letters an optional apostrophe-class character is allowed, which is what
    separates Jafar from Ja'far from Jaʿfar. Consonants that transliterate two
    ways (k/q, t/th, d/dh) expand to a class.

    The pattern is anchored at both ends and does NOT insert optional vowels
    between letters. An earlier version did, and a search for `Sindi` matched
    `Sending`, which is how a claim ends up citing a page that says nothing of
    the kind.
    """
    key = norm(term)
    # Real characters, not escapes: the same pattern string is handed to
    # Python's re and to ripgrep, and the two disagree about escape syntax.
    sep = "[" + AYN_HAMZA + "‐‑-]?"
    expand = {
        "k": "(?:k|q|kh)", "d": "(?:d|dh)", "t": "(?:t|th)",
        "s": "(?:s|sh|th)", "g": "(?:g|gh)", "f": "(?:f|ph)",
        "z": "(?:z|dh|d)", "i": "(?:i|y|ee|ie)", "u": "(?:u|w|oo|ou|o)",
        "a": "(?:a|aa)",
    }
    parts = []
    for ch in key:
        parts.append(expand.get(ch, re.escape(ch)))
        parts.append(sep)
    # a final -h is optional: Kazimiyya and Kazimiyyah are one word
    return r"\b" + "".join(parts[:-1]) + r"h?\b"


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-+", "-", s)
