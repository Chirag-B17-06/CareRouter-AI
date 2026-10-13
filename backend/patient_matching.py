"""Patient matching.

Names in speech transcripts vary in spelling ("Akshay"/"Akshai", "Mohammed"/"Muhammad"), so
matching is fuzzy - but a fuzzy name alone is *never* enough to link a conversation to a
medical record.  The result is a ranked candidate list with the signals that support each
candidate; a human must confirm any link made from a transcript.
"""
import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models_care import Patient

_HONORIFICS = {"mr", "mrs", "ms", "miss", "dr", "shri", "smt", "sri", "master", "baby", "late"}

NAME_STRONG_THRESHOLD = 0.88
DUPLICATE_THRESHOLD = 0.85


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t for t in text.split() if t not in _HONORIFICS]
    return " ".join(tokens)


_PHONETIC_SUBS = [
    ("ph", "f"), ("ck", "k"), ("kh", "k"), ("gh", "g"), ("th", "t"), ("dh", "d"), ("bh", "b"), ("sh", "s"),
    ("ch", "c"), ("w", "v"), ("z", "j"), ("q", "k"), ("x", "ks"), ("ee", "i"), ("oo", "u"), ("y", "i"),
]


def phonetic_key(name: str) -> str:
    """Cheap, vowel-insensitive key tolerant of common Indian-English spelling variants."""
    tokens = []
    for tok in normalize_name(name).split():
        for a, b in _PHONETIC_SUBS:
            tok = tok.replace(a, b)
        tok = re.sub(r"(.)\1+", r"\1", tok)                  # collapse doubles
        tok = tok[:1] + re.sub(r"[aeiou]", "", tok[1:])      # drop non-initial vowels
        tokens.append(tok)
    return " ".join(sorted(tokens))


def name_similarity(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    direct = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    token_overlap = len(ta & tb) / max(len(ta), len(tb))
    # A single given name matches a fuller name only weakly - this keeps "Akshay" from
    # being treated as the same person as "Akshay Kumar Rao" without corroboration.
    score = max(direct, 0.9 * token_overlap)
    if phonetic_key(na) == phonetic_key(nb):
        score = max(score, 0.9)
    return round(min(score, 1.0), 3)


def digits(phone: Optional[str]) -> str:
    return re.sub(r"\D", "", phone or "")[-10:]


def age_on(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


@dataclass
class MatchCandidate:
    patient_id: int
    patient_uid: str
    score: float
    signals: List[str] = field(default_factory=list)
    confidence_band: str = "low"        # high | medium | low
    display_name: str = ""
    identity_verified: bool = False


def find_candidates(
    db: Session, *, name: Optional[str] = None, dob: Optional[date] = None, age: Optional[int] = None,
    phone: Optional[str] = None, mrn: Optional[str] = None, limit: int = 5, today: Optional[date] = None,
) -> List[MatchCandidate]:
    today = today or date.today()
    pool = {}

    if mrn:
        for p in db.query(Patient).filter(Patient.mrn == mrn.strip(), Patient.status == "active"):
            pool[p.id] = p
    if phone and len(digits(phone)) >= 7:
        for p in db.query(Patient).filter(Patient.phone.like(f"%{digits(phone)[-7:]}"), Patient.status == "active"):
            pool[p.id] = p
    if name and normalize_name(name):
        tokens = normalize_name(name).split()
        pk = phonetic_key(name)
        clauses = [Patient.phonetic_key == pk] + [Patient.name_key.like(f"%{t}%") for t in tokens if len(t) >= 3]
        for p in db.query(Patient).filter(Patient.status == "active", or_(*clauses)).limit(200):
            pool[p.id] = p

    out: List[MatchCandidate] = []
    for p in pool.values():
        signals: List[str] = []
        score = 0.0
        sim = name_similarity(name, p.full_name) if name else 0.0
        if name and sim >= 0.6:
            signals.append(f"name_similarity:{sim:.2f}")
        score += 0.6 * sim

        corroborated = False
        if mrn and p.mrn and p.mrn == mrn.strip():
            signals.append("mrn_exact")
            score += 0.7
            corroborated = True
        if dob and p.date_of_birth:
            if dob == p.date_of_birth:
                signals.append("dob_exact")
                score += 0.3
                corroborated = True
            else:
                score -= 0.2
                signals.append("dob_conflict")
        elif age is not None and p.date_of_birth:
            if abs(age_on(p.date_of_birth, today) - age) <= 1:
                signals.append("age_consistent")
                score += 0.1
            else:
                score -= 0.15
                signals.append("age_conflict")
        if phone and p.phone and digits(phone) and digits(phone) == digits(p.phone):
            signals.append("phone_exact")
            score += 0.25
            corroborated = True

        score = round(max(0.0, min(score, 1.0)), 3)
        if score < 0.3:
            continue
        if corroborated and sim >= NAME_STRONG_THRESHOLD or ("mrn_exact" in signals and not name):
            band = "high"
        elif sim >= NAME_STRONG_THRESHOLD or corroborated:
            band = "medium"
        else:
            band = "low"
        out.append(MatchCandidate(
            patient_id=p.id, patient_uid=p.patient_uid, score=score, signals=signals, confidence_band=band,
            display_name=p.full_name, identity_verified=bool(p.identity_verified),
        ))

    out.sort(key=lambda c: (-c.score, c.patient_id))
    return out[:limit]


def likely_duplicates(db: Session, *, name: str, dob: Optional[date], phone: Optional[str],
                      mrn: Optional[str]) -> List[MatchCandidate]:
    """Candidates that should block silent creation of a new profile."""
    cands = find_candidates(db, name=name, dob=dob, phone=phone, mrn=mrn)
    return [
        c for c in cands
        if "mrn_exact" in c.signals
        or (any(s.startswith("name_similarity") for s in c.signals)
            and float(next(s for s in c.signals if s.startswith("name_similarity")).split(":")[1]) >= DUPLICATE_THRESHOLD
            and "dob_conflict" not in c.signals)
    ]
