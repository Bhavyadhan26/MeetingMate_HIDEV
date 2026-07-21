from __future__ import annotations

import re
from typing import Dict, Iterable, Tuple


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")
NAME_RE = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")
PROTECTED = {
    "We",
    "Decision",
    "Action",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
}


def _replace_matches(text: str, matches: Iterable[str], prefix: str, mapping: Dict[str, str]) -> str:
    for value in sorted(set(matches), key=len, reverse=True):
        if value in PROTECTED or value in mapping:
            continue
        token = f"[{prefix}_{sum(1 for item in mapping.values() if item.startswith('[' + prefix)) + 1}]"
        mapping[value] = token
        text = re.sub(rf"\b{re.escape(value)}\b", token, text)
    return text


def _replace_known_people(text: str, known_people: Iterable[str], mapping: Dict[str, str]) -> str:
    redacted = text
    for person in known_people:
        clean = person.strip()
        if not clean or clean in mapping:
            continue
        token = f"[PERSON_{len({item for item in mapping.values() if item.startswith('[PERSON')}) + 1}]"
        aliases = [clean]
        parts = clean.split()
        if len(parts) > 1:
            aliases.extend(parts)
        for alias in sorted(set(aliases), key=len, reverse=True):
            if alias in PROTECTED:
                continue
            mapping[alias] = token
            redacted = re.sub(rf"\b{re.escape(alias)}\b", token, redacted)
    return redacted


def redact_pii(text: str, known_people: Iterable[str] = ()) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}
    redacted = text
    redacted = _replace_matches(redacted, EMAIL_RE.findall(redacted), "EMAIL", mapping)
    redacted = _replace_matches(redacted, PHONE_RE.findall(redacted), "PHONE", mapping)
    redacted = _replace_known_people(redacted, known_people, mapping)
    candidates = [match.group(1) for match in NAME_RE.finditer(redacted) if not match.group(1).startswith("[")]
    redacted = _replace_matches(redacted, candidates, "PERSON", mapping)
    return redacted, mapping
