"""The Caldara–Iacoviello GPR dictionary (Table 1 of "Measuring Geopolitical
Risk", American Economic Review 2022, pp. 1194–1225).

Transcribed verbatim from the published table.  ``*`` is the truncation
character used in the paper (``threat*`` matches threat, threats,
threatening, ...).  Phrases in quotes are bigrams.
"""
from __future__ import annotations

# ----- Panel B: topic word sets ---------------------------------------------
WAR_WORDS = ["war", "conflict", "hostilities", "revolution*", "insurrection",
             "uprising", "revolt", "coup", "geopolitical"]
PEACE_WORDS = ["peace", "truce", "armistice", "treaty", "parley"]
MILITARY_WORDS = ["military", "troops", "missile*", '"arms"', "weapon*", "bomb*", "warhead*"]
NUCLEAR_BIGRAMS = ['"nuclear war*"', '"atomic war*"', '"nuclear missile*"', '"nuclear bomb*"',
                   '"atomic bomb*"', '"h-bomb*"', '"hydrogen bomb*"', '"nuclear test"',
                   '"nuclear weapon*"']
TERRORISM_WORDS = ["terror*", "guerrilla*", "hostage*"]
ACTOR_WORDS = ["allie*", "enem*", "insurgen*", "foe*", "army", "navy", "aerial", "troops", "rebels"]

# ----- Panel B: threat / act word sets ---------------------------------------
THREAT_WORDS = ["threat*", "warn*", "fear*", "risk*", "concern*", "danger*", "doubt*", "crisis",
                "troubl*", "disput*", "tension*", "imminen*", "inevitable", "footing", "menace*",
                "brink", "scare", "peril*"]
PEACE_DISRUPTION_WORDS = ["threat*", "menace*", "reject*", "peril*", "boycott*", "disrupt*"]
BUILDUP_WORDS = ["buildup*", "build-up*", "sanction*", "blockad*", "embargo", "quarantine",
                 "ultimatum", "mobiliz*"]
WAR_BEGIN_WORDS = ["begin*", "start*", "declar*", "begun", "began", "outbreak", '"broke out"',
                   "breakout", "proclamation", "launch*"]
ACTOR_FIGHT_WORDS = ["advance*", "attack*", "strike*", "drive*", "shell*", "offensive", "invasion",
                     "invad*", "clash*", "raid*", "launch*"]
TERRORISM_ACT_WORDS = ["attack", "act", "bomb*", "kill*", "strike*", "hijack*"]

# ----- Panel C: excluded words ----------------------------------------------
EXCLUSION_WORDS = ["movie*", "film*", "museum*", "anniversar*", "obituar*", "memorial*", "arts",
                   "book", "books", "memoir*", '"price war"', "game", "story", "history",
                   "veteran*", "tribute*", "sport", "music", "racing", "cancer", '"real estate"',
                   "mafia", "trial", "tax"]

# ----- Panel A: the eight search categories ----------------------------------
# (name, topic set, threat/act set, operator).  "N/2" is a proximity search
# (the two words within two words of each other); "AND" means both words
# appear anywhere in the same article.
CATEGORIES = [
    ("war_threats",      WAR_WORDS,       THREAT_WORDS,            "N/2"),
    ("peace_threats",    PEACE_WORDS,     PEACE_DISRUPTION_WORDS,  "N/2"),
    ("military_buildup", MILITARY_WORDS,  BUILDUP_WORDS,           "AND"),
    ("nuclear_threats",  NUCLEAR_BIGRAMS, THREAT_WORDS,            "AND"),
    ("terror_threats",   TERRORISM_WORDS, THREAT_WORDS,            "N/2"),
    ("war_begin",        WAR_WORDS,       WAR_BEGIN_WORDS,         "N/2"),
    ("war_escalation",   ACTOR_WORDS,     ACTOR_FIGHT_WORDS,       "N/2"),
    ("terror_acts",      TERRORISM_WORDS, TERRORISM_ACT_WORDS,     "N/2"),
]
THREAT_CATEGORIES = [c[0] for c in CATEGORIES[:5]]   # GPR Threats (GPRT)
ACT_CATEGORIES = [c[0] for c in CATEGORIES[5:]]      # GPR Acts (GPRA)
