import hashlib
import html
import re
import unicodedata

SPACE_RE = re.compile(r'\s+')
SENTENCE_RE = re.compile(r'(?<=[.!?。！？])\s+|\n+')


def normalize_space(value: str) -> str:
    return SPACE_RE.sub(' ', html.unescape(value or '')).strip()


def normalize_for_dedup(value: str) -> str:
    value = unicodedata.normalize('NFKC', normalize_space(value)).casefold()
    value = re.sub(r'[^\w가-힣]+', ' ', value)
    return SPACE_RE.sub(' ', value).strip()


def dedup_hash(text: str, url: str = '') -> str:
    key = normalize_for_dedup(text)
    if not key:
        key = normalize_for_dedup(url)
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


def split_sentences(text: str) -> list[str]:
    parts = [normalize_space(p) for p in SENTENCE_RE.split(text or '')]
    return [p for p in parts if 8 <= len(p) <= 1200]


def contains_any(text: str, terms: list[str]) -> bool:
    folded = (text or '').casefold()
    return any(term.casefold() in folded for term in terms if term)
