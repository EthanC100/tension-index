"""Translate the GPR dictionary into GDELT DOC API queries.

Two things differ between the newspaper archives GPR is run on and the GDELT
DOC API, and both are handled here:

* **No truncation.**  The DOC API ignores the ``*`` wildcard, so every stem in
  the GPR lists is expanded into an explicit set of inflections
  (``threat*`` -> threat, threats, threaten, threatened, ...).
* **Query shape.**  GPR's ``N/2`` proximity searches need one ``nearN:"a b"``
  clause per (topic word, threat word) pair, which makes queries long.  The
  builder offers a ``boolean`` mode (both word sets anywhere in the article)
  and a ``proximity`` mode (pairs within a few words of each other, split
  into several requests when the query would be too long).
"""
from __future__ import annotations

from itertools import product

from . import wordlists as W

# Explicit inflections for every truncated stem in Table 1.  Keys are the
# exact tokens used in the published word lists.
INFLECTIONS: dict[str, list[str]] = {
    "revolution*": ["revolution", "revolutions", "revolutionary"],
    "missile*": ["missile", "missiles"],
    "weapon*": ["weapon", "weapons", "weaponry"],
    "bomb*": ["bomb", "bombs", "bombing", "bombings", "bombed", "bomber", "bombers"],
    "warhead*": ["warhead", "warheads"],
    "terror*": ["terror", "terrorism", "terrorist", "terrorists"],
    "guerrilla*": ["guerrilla", "guerrillas"],
    "hostage*": ["hostage", "hostages"],
    "allie*": ["allies", "allied"],
    "enem*": ["enemy", "enemies"],
    "insurgen*": ["insurgent", "insurgents", "insurgency"],
    "foe*": ["foe", "foes"],
    "threat*": ["threat", "threats", "threaten", "threatens", "threatened", "threatening"],
    "warn*": ["warn", "warns", "warned", "warning", "warnings"],
    "fear*": ["fear", "fears", "feared", "fearing", "fearful"],
    "risk*": ["risk", "risks", "risked", "risky"],
    "concern*": ["concern", "concerns", "concerned", "concerning"],
    "danger*": ["danger", "dangers", "dangerous"],
    "doubt*": ["doubt", "doubts", "doubted", "doubtful"],
    "troubl*": ["trouble", "troubles", "troubled", "troubling"],
    "disput*": ["dispute", "disputes", "disputed"],
    "tension*": ["tension", "tensions"],
    "imminen*": ["imminent", "imminence"],
    "menace*": ["menace", "menaces", "menaced", "menacing"],
    "peril*": ["peril", "perils", "perilous"],
    "reject*": ["reject", "rejects", "rejected", "rejection"],
    "boycott*": ["boycott", "boycotts", "boycotted"],
    "disrupt*": ["disrupt", "disrupts", "disrupted", "disruption"],
    "buildup*": ["buildup", "buildups"],
    "build-up*": ["build-up", "build-ups"],
    "sanction*": ["sanction", "sanctions", "sanctioned"],
    "blockad*": ["blockade", "blockades", "blockaded"],
    "mobiliz*": ["mobilize", "mobilized", "mobilization", "mobilise", "mobilised", "mobilisation"],
    "begin*": ["begin", "begins", "beginning"],
    "start*": ["start", "starts", "started", "starting"],
    "declar*": ["declare", "declares", "declared", "declaration"],
    "launch*": ["launch", "launches", "launched", "launching"],
    "advance*": ["advance", "advances", "advanced"],
    "attack*": ["attack", "attacks", "attacked", "attacking"],
    "strike*": ["strike", "strikes", "striking"],
    "drive*": ["drive", "drives", "driven"],
    "shell*": ["shell", "shells", "shelled", "shelling"],
    "invad*": ["invade", "invades", "invaded", "invading"],
    "clash*": ["clash", "clashes", "clashed"],
    "raid*": ["raid", "raids", "raided"],
    "kill*": ["kill", "kills", "killed", "killing", "killings"],
    "hijack*": ["hijack", "hijacked", "hijacking"],
    '"nuclear war*"': ['"nuclear war"', '"nuclear wars"', '"nuclear warfare"'],
    '"atomic war*"': ['"atomic war"', '"atomic warfare"'],
    '"nuclear missile*"': ['"nuclear missile"', '"nuclear missiles"'],
    '"nuclear bomb*"': ['"nuclear bomb"', '"nuclear bombs"'],
    '"atomic bomb*"': ['"atomic bomb"', '"atomic bombs"'],
    '"h-bomb*"': ['"h-bomb"', '"h-bombs"'],
    '"hydrogen bomb*"': ['"hydrogen bomb"', '"hydrogen bombs"'],
    '"nuclear weapon*"': ['"nuclear weapon"', '"nuclear weapons"'],
    "movie*": ["movie", "movies"],
    "film*": ["film", "films"],
    "museum*": ["museum", "museums"],
    "anniversar*": ["anniversary", "anniversaries"],
    "obituar*": ["obituary", "obituaries"],
    "memorial*": ["memorial", "memorials"],
    "memoir*": ["memoir", "memoirs"],
    "veteran*": ["veteran", "veterans"],
    "tribute*": ["tribute", "tributes"],
}


def expand(term: str) -> list[str]:
    if term in INFLECTIONS:
        return INFLECTIONS[term]
    assert "*" not in term, f"no inflections defined for {term}"
    return [term]


def expand_set(terms: list[str]) -> list[str]:
    out: list[str] = []
    for t in terms:
        for f in expand(t):
            if f not in out:
                out.append(f)
    return out


def _or_group(forms: list[str]) -> str:
    return "(" + " OR ".join(forms) + ")"


def exclusion_clause() -> str:
    return " ".join(f"-{f}" for f in expand_set(W.EXCLUSION_WORDS))


def lang_clause(english_only: bool) -> str:
    return " sourcelang:english" if english_only else ""


def boolean_query(category: str, english_only: bool = True, exclude: bool = True) -> str:
    """Both word sets anywhere in the same article (GPR's AND categories
    exactly; an approximation of the N/2 categories)."""
    name, topic, other, _op = next(c for c in W.CATEGORIES if c[0] == category)
    q = f"{_or_group(expand_set(topic))} {_or_group(expand_set(other))}"
    if exclude:
        q += " " + exclusion_clause()
    return q + lang_clause(english_only)


def union_boolean_query(english_only: bool = True, exclude: bool = True) -> str:
    """OR of the eight boolean categories, for the 'any category' share."""
    parts = []
    for name, topic, other, _op in W.CATEGORIES:
        parts.append(f"({_or_group(expand_set(topic))} {_or_group(expand_set(other))})")
    q = "(" + " OR ".join(parts) + ")"
    if exclude:
        q += " " + exclusion_clause()
    return q + lang_clause(english_only)


def _near_forms(forms: list[str]) -> list[str]:
    # near:"..." takes bare words; multi-word phrases are kept as their words.
    return [f.strip('"') for f in forms]


def proximity_queries(category: str, window: int = 3, english_only: bool = True,
                      exclude: bool = True, max_len: int = 1800) -> list[str]:
    """GPR N/2 search as OR-ed nearN clauses, chunked by topic word so each
    request stays under ``max_len`` characters.  For the two AND categories
    this returns the boolean query."""
    name, topic, other, op = next(c for c in W.CATEGORIES if c[0] == category)
    if op == "AND":
        return [boolean_query(category, english_only, exclude)]
    suffix = (" " + exclusion_clause() if exclude else "") + lang_clause(english_only)
    clauses = [f'near{window}:"{a} {b}"' for a, b in product(_near_forms(expand_set(topic)),
                                                               _near_forms(expand_set(other)))]
    queries, cur = [], []
    for c in clauses:
        trial = "(" + " OR ".join(cur + [c]) + ")" + suffix
        if cur and len(trial) > max_len:
            queries.append("(" + " OR ".join(cur) + ")" + suffix)
            cur = [c]
        else:
            cur.append(c)
    if cur:
        queries.append("(" + " OR ".join(cur) + ")" + suffix)
    return queries


if __name__ == "__main__":  # quick inspection
    for cat, *_ in W.CATEGORIES:
        bq = boolean_query(cat)
        pq = proximity_queries(cat)
        print(f"{cat}: boolean {len(bq)} chars; proximity {len(pq)} request(s), {sum(map(len, pq))} chars")
    print("union:", len(union_boolean_query()), "chars")
    print(boolean_query("war_threats"))
