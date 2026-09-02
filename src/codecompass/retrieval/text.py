"""Deterministic text preparation for code retrieval experiments."""

from __future__ import annotations

import re
import unicodedata

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_NON_IDENTIFIER = re.compile(r"[^\w]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+", re.UNICODE)


def normalize_retrieval_text(text: str) -> str:
    """Normalize Unicode and Persian spacing without translating content."""
    normalized = _normalize_unicode(text)
    return _WHITESPACE.sub(" ", normalized).strip().casefold()


def identifier_terms(text: str) -> tuple[str, ...]:
    """Return original and deterministic snake/camel identifier terms."""
    normalized = _normalize_unicode(text)
    terms: list[str] = []
    for token in _NON_IDENTIFIER.split(normalized):
        if not token:
            continue
        split = _CAMEL_BOUNDARY.sub(" ", token.replace("_", " "))
        for value in (token, *split.split()):
            value = value.casefold()
            if value and value not in terms:
                terms.append(value)
    return tuple(terms)


def _normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text).translate(
        str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "\u200c": " "})
    )
