"""Deterministic keyword extraction (TF with stopword filtering).

Topics/keywords are derived without any AI component so the graph builder
and auto-tagging stay fully offline and reproducible.

CJK text has no whitespace word boundaries. Instead of slicing arbitrary
fixed-width chunks (which produced nonsense "topics" such as ``不与任何``),
we only consider two-character phrases at the *edges* of a CJK run — those
are almost always real words at a clause boundary — and require the phrase
to occur more than once in the document.
"""

from __future__ import annotations

import re
from collections import Counter

_LATIN_RE = re.compile(r"[a-zA-Z][\w'-]*")
_CJK_RUN_RE = re.compile(r"[\u3400-\u9fff]+")

#: Characters that never start/end a meaningful Chinese keyword.
_CJK_FUNCTION_CHARS = frozenset(
    "的了和与在是之为以及对其这那些个们很更最都就还又等后时上下内外"
    "并或而被把让使于由且不但如若因而所以可以一些每种各不无也字中及"
    "一二三四五六七八九十第将已会将能可会对于把从到让使把被给向"
)

#: Compact English stopword list (deterministic, no external data files).
STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are aren as at be because
    been before being below between both but by can cannot could couldn did didn
    do does doesn doing don down during each few for from further had hadn has
    hasn have haven having he her here hers herself him himself his how i if in
    into is isn it its itself just ll me more most mustn my myself no nor not now
    of off on once only or other our ours ourselves out over own re s same shan
    she should shouldn so some such t than that the their theirs them themselves
    then there these they this those through to too under until up ve very was
    wasn we were weren what when where which while who whom why will with won
    would wouldn you your yours yourself yourselves also may many upon within
    without however therefore thus among across per etc via using use used one
    two three new like get got make made see seen way well even much still back
    go going came come want needs need let ll re
    """.split()
)

_MIN_TOKEN_LEN = 3
_MIN_CJK_FREQUENCY = 2


def extract_keywords(text: str, *, limit: int = 8) -> list[str]:
    """Top-N significant terms of *text*, most frequent first.

    Deterministic: ties are broken alphabetically.
    """
    counts: Counter[str] = Counter()
    for token in _LATIN_RE.findall(text):
        token = token.lower().strip("'-")
        if len(token) < _MIN_TOKEN_LEN or token in STOPWORDS:
            continue
        counts[token] += 1

    cjk: Counter[str] = Counter()
    for run in _CJK_RUN_RE.findall(text):
        if len(run) < 2:
            continue
        for phrase in {run[:2], run[-2:]}:
            if phrase[0] in _CJK_FUNCTION_CHARS or phrase[1] in _CJK_FUNCTION_CHARS:
                continue
            cjk[phrase] += 1
    for phrase, frequency in cjk.items():
        if frequency >= _MIN_CJK_FREQUENCY:
            counts[phrase] += frequency

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:limit]]
