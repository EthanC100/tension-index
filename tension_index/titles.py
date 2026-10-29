"""Apply the GPR dictionary literally to article headlines.

GKG records carry the page title (``<PAGE_TITLE>`` in the Extras field) from
about September 2019.  Headlines are short, so the GPR rules can be applied
exactly as written in Table 1:

* ``term*`` is a prefix match, a bare term an exact token match, a quoted
  phrase a consecutive-token match;
* ``N/2`` = a topic term and a threat/act term with at most two words between
  them, in either order;
* ``AND`` = both anywhere in the headline;
* any excluded word anywhere in the headline removes the article.
"""
from __future__ import annotations

import re

from . import wordlists as W

TOKEN_RE = re.compile(r"[a-z]+(?:-[a-z]+)*")
TITLE_RE = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.S)


class Term:
    def __init__(self, raw: str):
        raw = raw.strip()
        phrase = raw.strip('"')
        self.prefix = phrase.endswith("*")
        self.words = phrase.rstrip("*").lower().split()

    def positions(self, toks: list[str]) -> list[tuple[int, int]]:
        """(start, end) token spans where the term occurs."""
        n = len(self.words)
        out = []
        for i in range(len(toks) - n + 1):
            ok = True
            for k, w in enumerate(self.words):
                t = toks[i + k]
                last = k == n - 1
                if last and self.prefix:
                    if not t.startswith(w):
                        ok = False
                        break
                elif t != w:
                    ok = False
                    break
            if ok:
                out.append((i, i + n - 1))
        return out


def _compile(terms: list[str]) -> list[Term]:
    return [Term(t) for t in terms]


COMPILED = [(name, _compile(topic), _compile(other), op) for name, topic, other, op in W.CATEGORIES]
EXCLUDE = _compile(W.EXCLUSION_WORDS)
CATEGORY_NAMES = [c[0] for c in W.CATEGORIES]


# Fast pre-filter: a headline can only match if it contains a topic term.
_TOPIC_EXACT = {t.words[0] for _n, topic, _o, _op in COMPILED for t in topic if not (t.prefix and len(t.words) == 1)}
_TOPIC_PREFIX = tuple(t.words[0] for _n, topic, _o, _op in COMPILED for t in topic if t.prefix and len(t.words) == 1)


def _may_match(toks: list[str]) -> bool:
    return any(t in _TOPIC_EXACT or t.startswith(_TOPIC_PREFIX) for t in toks)


def tokenize(title: str) -> list[str]:
    return TOKEN_RE.findall(title.lower())


def _spans(terms: list[Term], toks: list[str]) -> list[tuple[int, int]]:
    out = []
    for t in terms:
        out.extend(t.positions(toks))
    return out


def classify(title: str) -> dict[str, bool]:
    """Which GPR categories a headline falls in (all False if excluded)."""
    toks = tokenize(title)
    res = {name: False for name in CATEGORY_NAMES}
    if not toks or not _may_match(toks) or _spans(EXCLUDE, toks):
        return res
    for name, topic, other, op in COMPILED:
        a = _spans(topic, toks)
        if not a:
            continue
        b = _spans(other, toks)
        if not b:
            continue
        if op == "AND":
            res[name] = True
            continue
        # N/2: at most two intervening words, either order.
        for s1, e1 in a:
            for s2, e2 in b:
                gap = s2 - e1 - 1 if s2 > e1 else s1 - e2 - 1
                if (s1, e1) != (s2, e2) and gap <= 2:
                    res[name] = True
                    break
            if res[name]:
                break
    return res


def extract_title(extras: str) -> str | None:
    m = TITLE_RE.search(extras)
    if not m:
        return None
    import html
    return html.unescape(m.group(1)).strip()


# Looser headline variants (headlines are short, so the strict GPR rules
# match few of them).  ``and``: topic and threat/act word anywhere in the
# headline for every category.  ``topic``: any word from the war, military,
# nuclear or terrorism topic sets.
TOPIC_SETS = _compile(W.WAR_WORDS + W.MILITARY_WORDS + W.NUCLEAR_BIGRAMS + W.TERRORISM_WORDS)


def classify_variants(title: str) -> dict[str, bool]:
    toks = tokenize(title)
    out = {"and": False, "topic": False}
    if not toks or not _may_match(toks) or _spans(EXCLUDE, toks):
        return out
    out["topic"] = bool(_spans(TOPIC_SETS, toks))
    for _name, topic, other, _op in COMPILED:
        if _spans(topic, toks) and _spans(other, toks):
            out["and"] = True
            break
    return out
