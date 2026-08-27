"""The writing rules, enforced. Any violation fails the build.

    python tools/lint_prose.py --post musa-custody
    python tools/lint_prose.py --post musa-custody --report   # do not fail

These rules govern the prose written for this account. They are mechanical on
purpose: a rule a machine can check is a rule that holds at 3am, and the ones
that cannot be checked mechanically are checked by the human who reads the
draft. Where a check can only approximate a rule, it says so in its message
and is emitted as a WARN rather than a FAIL.

Findings come in two levels:

    FAIL   blocks the render
    WARN   printed, does not block. Every WARN is a judgement call a human
           has to make, and the tool refuses to make it silently.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from sourcelib import norm  # noqa: E402

PLACEHOLDER = re.compile(r"\[\[NEEDS CLAIM:.*?\]\]", re.S)

EM_DASH = re.compile(r"[—–]|(?<=\s)--(?=\s)")

# -ly words that are not adverbs. Everything else ending in -ly is flagged.
NOT_ADVERBS = {
    "only", "early", "holy", "family", "reply", "supply", "apply", "italy",
    "july", "ally", "rely", "ugly", "assembly", "monopoly", "belly",
    "melancholy", "anomaly", "wholly",
    # Verbs and nouns that end in -ly and are not adverbs at all.
    "imply", "implies", "comply", "multiply", "reply", "supply", "apply",
    "assembly", "homily", "family", "italy", "jelly", "rally", "tally",
    "ply", "fly", "sly", "lily",
}

PASSIVE = re.compile(
    r"\b(?:was|were|is|are|been|being|be)\s+(?:\w+ly\s+)?"
    r"(?:\w+ed|known|written|built|laid|taken|given|made|held|put|sent|said|"
    r"brought|kept|found|left|told|shown|seen|born|struck|drawn|thrown)\b",
    re.I)

NOT_X_ITS_Y = re.compile(
    r"\bnot\s+[^.;]{2,70}?,\s*(?:it'?s|it is|they'?re|they are|but|rather)\b", re.I)

THROAT_CLEARING = re.compile(
    r"^\s*(?:there (?:is|are|was|were)\b|it (?:is|was) (?:often|widely|commonly|"
    r"important|worth|no)\b|in the (?:early|late|history|world)\b|"
    r"one of the\b|for centuries\b|throughout (?:history|the)\b|"
    r"history (?:is|has|shows|remembers)\b|many (?:people|historians|of)\b|"
    r"today\b|when we\b|we (?:often|tend|think|know)\b|"
    r"to understand\b|before we\b)", re.I)

VAGUE = [
    "the early muslim world", "the muslim world", "the islamic world",
    "early islam", "the medieval world", "the ancient world",
    "the region", "the era", "the period", "the time period",
    "the arab world", "the east", "the west", "society at the time",
    "in those days", "back then",
]

PRAISE = {
    "great", "glorious", "noble", "blessed", "magnificent", "illustrious",
    "revered", "saintly", "brave", "wise", "beloved", "holy", "pure",
    "flawless", "perfect", "immortal", "legendary", "heroic", "pious",
    "righteous", "exalted", "sublime", "infallible",
}

DISPARAGE = {
    "tyrant", "tyrannical", "evil", "wicked", "villain", "corrupt",
    "heretic", "heretics", "deviant", "misguided", "fanatic", "fanatics",
    "barbaric", "savage",
}

PREACHING = re.compile(
    r"\b(?:we must|we should|let us|remember that|never forget|O reader|"
    r"may (?:god|allah)|peace be upon|upon him be peace|\(a\.?s\.?\)|"
    r"\(pbuh\)|\(s\.?a\.?w\.?\)|alayhi(?:s)? salam|salla allahu|"
    r"our (?:beloved|master)|the truth is that)\b", re.I)

BELIEF_REQUIRED = re.compile(
    r"\b(?:divinely appointed|by divine command|god chose|allah chose|"
    r"through divine|miraculous(?:ly)?|the infallible)\b", re.I)

ATTRIBUTION = re.compile(
    r"\b(?:al-\w+|ibn \w+|abu \w+|shaykh \w+|the chronicle|the chronicler|"
    r"\w+ (?:puts|places|gives|reports|records|writes|names|dates|counts))\b",
    re.I)

CITATION_LABEL = re.compile(
    r"^\s*(?:source|sources|see|cf\.|ref\.|citation)\b[:.]?", re.I)

QUOTE = re.compile(r"[“\"]([^“”\"]{2,600})[”\"]")

DISAGREE = re.compile(
    r"\b(?:disagree|disagrees|differs?|differ|contradicts?|"
    r"another (?:account|chronicle|report)|others? (?:say|put|give|report)|"
    r"one (?:account|chronicle|report).{0,40}another)\b", re.I)

DATE_TOKEN = re.compile(r"\b(?:\d{1,4}\s*(?:AH|A\.H\.|CE|C\.E\.|BCE)|\d{3,4})\b")

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "by",
    "for", "with", "from", "as", "that", "this", "it", "he", "she", "they",
    "his", "her", "their", "was", "were", "is", "are", "had", "has", "have",
    "not", "no", "who", "whom", "which", "when", "where", "what", "why", "how",
    "then", "than", "into", "over", "after", "before", "out", "up", "down",
    "one", "two", "three", "him", "them", "its", "would", "could", "did",
    "does", "do", "been", "being", "be", "there", "here", "any", "all", "some",
}


@dataclass
class Finding:
    level: str          # FAIL | WARN
    slide: int | None
    rule: str
    message: str

    def __str__(self) -> str:
        where = f"slide {self.slide}" if self.slide is not None else "post"
        return f"{self.level:<4} {where:<9} {self.rule:<22} {self.message}"


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z'’-]+", text)


def content_words(text: str) -> set[str]:
    return {norm(w) for w in words(text)
            if w.lower() not in STOPWORDS and len(w) > 3}


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text.strip()) if s.strip()]


# --------------------------------------------------------------------------
# structure

def check_structure(post, slides, out: list[Finding]) -> None:
    title = post["cover_title"]
    if title != title.lower():
        out.append(Finding("FAIL", None, "cover-title-case",
                           f"cover title must be lowercase: {title!r}"))
    if len(title.split()) >= 8:
        out.append(Finding("FAIL", None, "cover-title-length",
                           f"cover title is {len(title.split())} words, the limit is 7"))
    for phrase in VAGUE + ["century", "centuries", "empire", "civilisation",
                           "civilization", "dynasty", "history of"]:
        if phrase in title.lower():
            out.append(Finding("FAIL", None, "cover-title-vague",
                               f"cover title names a region or a century: {phrase!r}. "
                               f"Name a thing: 'the road from kufa'."))

    n = len(slides)
    if not 12 <= n <= 20:
        out.append(Finding("FAIL", None, "slide-count",
                           f"{n} slides. The range is 12 to 20."))
    if slides and slides[0]["template"] != "cover":
        out.append(Finding("FAIL", 1, "slide-1-template",
                           "slide 1 must use the cover template"))
    if len(slides) > 1 and slides[1]["template"] != "question":
        out.append(Finding("FAIL", 2, "slide-2-question",
                           f'slide 2 is {slides[1]["template"]}. Slide 2 is always '
                           f"the question template."))
    if len(slides) > 1 and "?" not in slides[1]["body"]:
        out.append(Finding("FAIL", 2, "slide-2-question",
                           "slide 2 carries no question mark. It has to ask the "
                           "question the rest of the carousel answers."))
    if slides and slides[-1]["template"] != "closing":
        out.append(Finding("FAIL", n, "closing-template",
                           "the last slide must use the closing template"))

    if not post["running_head"].strip():
        out.append(Finding("FAIL", None, "running-head",
                           "the post has no running head. Every interior slide "
                           "carries it, so any screenshot is branded."))


def check_chain(slides, out: list[Finding]) -> None:
    """Every interior slide names or answers the one before it.

    Approximated by lexical linkage: an interior slide that shares no content
    word with the slide before it is probably an item in a list rather than a
    step in an argument. This is the rule that most needs a human eye, so it
    is a WARN, and the message says what to check.
    """
    orphans = []
    for i in range(2, len(slides)):
        prev, cur = slides[i - 1], slides[i]
        shared = content_words(prev["body"]) & content_words(cur["body"])
        if not shared:
            orphans.append(cur["position"])
            out.append(Finding("WARN", cur["position"], "chain-break",
                               f'shares no word with slide {prev["position"]}. '
                               f"Read them together: if this slide would survive "
                               f"deleting that one, the essay is a list."))
    if len(slides) > 4 and len(orphans) >= max(2, (len(slides) - 2) // 3):
        out.append(Finding("FAIL", None, "chain-break",
                           f"{len(orphans)} interior slides connect to nothing "
                           f"before them ({', '.join(map(str, orphans))}). That is "
                           f"a list, not an essay."))

    # The stated test: slide 4 should not make complete sense with slide 1 gone.
    if len(slides) >= 4:
        four = content_words(slides[3]["body"])
        earlier = content_words(slides[1]["body"]) | content_words(slides[2]["body"])
        if not (four & earlier):
            out.append(Finding("FAIL", slides[3]["position"], "slide-4-standalone",
                               "slide 4 reads fine with the opening removed. It has "
                               "to depend on what came before it."))


def check_subjects(slides, claims, out: list[Finding]) -> None:
    """At most three distinct subjects per carousel."""
    subjects = {c["subject"] for c in claims if c["subject"]}
    if len(subjects) > 3:
        out.append(Finding("FAIL", None, "three-subjects",
                           f"{len(subjects)} claim subjects: "
                           f'{", ".join(sorted(subjects))}. The limit is three.'))
        return
    # No claims yet? Fall back to proper nouns that recur across slides.
    if not subjects:
        seen = Counter()
        for s in slides:
            names = set(re.findall(r"\b(?:al-|ibn |abu )?[A-Z][a-z']{2,}", s["body"]))
            for name in names:
                seen[norm(name)] += 1
        recurring = [n for n, c in seen.items() if c >= 3]
        if len(recurring) > 3:
            out.append(Finding("WARN", None, "three-subjects",
                               f"{len(recurring)} names recur across three or more "
                               f"slides. Three subjects is the ceiling; check "
                               f"whether this is one essay or two."))


def check_closing(slides, out: list[Finding]) -> None:
    if not slides:
        return
    closing = slides[-1]
    body = closing["body"].lower()
    for marker in ("in short", "in sum", "in conclusion", "to summarise",
                   "to summarize", "in the end", "all in all", "this is why",
                   "and so, ", "ultimately"):
        if marker in body:
            out.append(Finding("FAIL", closing["position"], "closing-summary",
                               f"the closing reads as a summary ({marker!r}). It "
                               f"states the thing nobody repeats."))
    earlier = set()
    for s in slides[:-1]:
        earlier |= content_words(s["body"])
    own = content_words(closing["body"])
    if own and len(own & earlier) / len(own) > 0.8:
        out.append(Finding("WARN", closing["position"], "closing-summary",
                           "every word in the closing already appeared. A closing "
                           "that repeats is a summary."))


# --------------------------------------------------------------------------
# sentences

def check_sentences(slides, out: list[Finding]) -> None:
    for s in slides:
        pos, body = s["position"], s["body"]

        if EM_DASH.search(body):
            out.append(Finding("FAIL", pos, "em-dash", "em dash. Use a full stop."))

        for m in PASSIVE.finditer(body):
            out.append(Finding("WARN", pos, "passive-voice",
                               f"{m.group(0)!r}. Name the person who did it: "
                               f"al-Mansur laid out the city."))

        for w in words(body):
            lw = w.lower()
            if lw.endswith("ly") and lw not in NOT_ADVERBS and len(lw) > 4:
                out.append(Finding("FAIL", pos, "adverb", f"adverb: {w!r}"))

        if NOT_X_ITS_Y.search(body):
            out.append(Finding("FAIL", pos, "not-x-its-y",
                               "'not X, it's Y' construction. State the thing."))

        if s["template"] != "cover" and THROAT_CLEARING.search(body):
            out.append(Finding("FAIL", pos, "throat-clearing",
                               f"opens on throat-clearing: {body[:44]!r}. Start on "
                               f"the fact."))

        low = body.lower()
        for phrase in VAGUE:
            if phrase in low:
                out.append(Finding("FAIL", pos, "vague-noun",
                                   f"{phrase!r}. Name it: Baghdad, Kufa, 148 AH."))

        if s["template"] == "body":
            n = len(body.split())
            if not 60 <= n <= 100:
                out.append(Finding("FAIL", pos, "body-length",
                                   f"{n} words. A body slide runs 60 to 100."))

        sents = sentences(body)
        if len(sents) >= 3:
            lengths = [len(x.split()) for x in sents]
            mean = sum(lengths) / len(lengths)
            if all(abs(x - mean) <= 5 for x in lengths):
                out.append(Finding("FAIL", pos, "sentence-rhythm",
                                   f"every sentence is within five words of the "
                                   f"mean ({mean:.0f}). Vary the length."))


# --------------------------------------------------------------------------
# evidence

def check_evidence(post, slides, claims, out: list[Finding]) -> None:
    for s in slides:
        pos, body = s["position"], s["body"]
        if CITATION_LABEL.match(body):
            out.append(Finding("FAIL", pos, "citation-label",
                               "citation label slide. Attribution lives inside "
                               "the sentence: 'al-Tabari puts the number at'."))
        for m in QUOTE.finditer(body):
            n = len(m.group(1).split())
            if n > 15:
                out.append(Finding("FAIL", pos, "long-quote",
                                   f"{n}-word quotation. The limit is fifteen. "
                                   f"Paraphrase entirely or quote short."))

    disputed = [c for c in claims if (c["dispute_note"] or "").strip()]
    if disputed:
        named = any(DISAGREE.search(s["body"]) for s in slides)
        if not named:
            ids = ", ".join(c["id"] for c in disputed)
            out.append(Finding("FAIL", None, "unnamed-dispute",
                               f"{ids} carry a dispute note and no slide says the "
                               f"chronicles disagree. Name both accounts."))

    if post["pillar"] == "number":
        joined = " ".join(s["body"] for s in slides)
        dates = set(DATE_TOKEN.findall(joined))
        if len(dates) < 2:
            out.append(Finding("FAIL", None, "number-card",
                               "a number post states the arithmetic and the two "
                               "dates it spans. Fewer than two dates appear."))
        if not re.search(r"\d+\s*(?:-|minus|to|from)\s*\d+|\d+\s*years", joined, re.I):
            out.append(Finding("FAIL", None, "number-card",
                               "a number post states the arithmetic, not only the "
                               "result."))

    attributed = sum(1 for s in slides if ATTRIBUTION.search(s["body"]))
    if len(slides) > 4 and attributed < 2:
        out.append(Finding("WARN", None, "attribution",
                           f"only {attributed} slides name who says so. Attribution "
                           f"belongs inside the sentence."))


# --------------------------------------------------------------------------
# register

def check_register(slides, out: list[Finding]) -> None:
    for s in slides:
        pos, body = s["position"], s["body"]
        for w in words(body):
            lw = w.lower()
            if lw in PRAISE:
                out.append(Finding("FAIL", pos, "praise-adjective",
                                   f"{w!r}. Evidence does that work."))
            if lw in DISPARAGE:
                out.append(Finding("FAIL", pos, "disparagement",
                                   f"{w!r}. Argue from evidence."))
        if PREACHING.search(body):
            out.append(Finding("FAIL", pos, "preaching",
                               f"{PREACHING.search(body).group(0)!r}. The account "
                               f"argues; it does not preach."))
        if BELIEF_REQUIRED.search(body):
            out.append(Finding("FAIL", pos, "requires-belief",
                               f"{BELIEF_REQUIRED.search(body).group(0)!r}. Write "
                               f"for a stranger with no attachment to the tradition."))


def check_placeholders(slides, out: list[Finding]) -> None:
    for s in slides:
        for m in PLACEHOLDER.finditer(s["body"]):
            out.append(Finding("FAIL", s["position"], "needs-claim",
                               f"{m.group(0)[:70]} - a placeholder is correct in a "
                               f"draft and fatal in a render."))


def check_post(post, slides, claims) -> list[Finding]:
    out: list[Finding] = []
    check_structure(post, slides, out)
    check_chain(slides, out)
    check_subjects(slides, claims, out)
    check_closing(slides, out)
    check_sentences(slides, out)
    check_evidence(post, slides, claims, out)
    check_register(slides, out)
    check_placeholders(slides, out)
    return out


def load(conn: sqlite3.Connection, post_id: str):
    post = conn.execute("SELECT * FROM post WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        raise SystemExit(f"no post {post_id}")
    slides = list(conn.execute(
        "SELECT * FROM slide WHERE post_id = ? ORDER BY position", (post_id,)))
    claims = list(conn.execute(
        """SELECT c.* FROM claim c JOIN post_claim pc ON pc.claim_id = c.id
           WHERE pc.post_id = ?""", (post_id,)))
    return post, slides, claims


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="enforce the writing rules")
    ap.add_argument("--post", required=True)
    ap.add_argument("--db", default=str(ROOT / "claims.db"))
    ap.add_argument("--report", action="store_true",
                    help="print findings and exit 0. For working on a draft.")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    findings = check_post(*load(conn, a.post))
    for f in findings:
        print(f)
    fails = [f for f in findings if f.level == "FAIL"]
    warns = [f for f in findings if f.level == "WARN"]
    print(f"\n{len(fails)} FAIL, {len(warns)} WARN")
    return 1 if fails and not a.report else 0


if __name__ == "__main__":
    raise SystemExit(main())
