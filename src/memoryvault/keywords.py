"""Deterministic keyword extraction (TF with stopword filtering).

Topics/keywords are derived without any AI component so the graph builder
and auto-tagging stay fully offline and reproducible.
"""

from __future__ import annotations

import re
from collections import Counter

_WORD_RE = re.compile(r"[a-zA-Z][\w'-]*|[\u4e00-\u9fff]{1,4}", re.UNICODE)

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


def extract_keywords(text: str, *, limit: int = 8) -> list[str]:
    """Top-N significant terms of *text*, most frequent first.

    Deterministic: ties are broken alphabetically.
    """
    counts: Counter[str] = Counter()
    for token in _WORD_RE.findall(text):
        token = token.lower().strip("'-")
        if len(token) < _MIN_TOKEN_LEN or token in STOPWORDS:
            continue
        counts[token] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:limit]]
