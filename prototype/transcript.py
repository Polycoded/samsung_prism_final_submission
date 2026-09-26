"""Conservative, corpus-derived text corrections; no generative rewriting."""
import re


_CORRECTION_VALUE = r"[A-Za-z0-9][A-Za-z0-9:.%'-]*"


def _normalize_explicit_value_correction(text):
    """Resolve a tightly local, explicitly marked value correction.

    The patterns deliberately accept only one-token values. This covers numbers,
    weekdays, short names, and times without attempting open-ended semantic
    rewriting. Product-like values remain in the corpus-alias correction path so
    an unknown sibling model still triggers clarification instead of retrieval.
    """
    correction = re.compile(
        rf"(?P<old>\b{_CORRECTION_VALUE}\b)\s*(?:—|–|-|,)\s*"
        rf"(?:sorry(?:\s*,?\s*I\s+meant)?|no|I\s+mean|actually|make\s+that)\s*,?\s*"
        rf"(?P<new>\b{_CORRECTION_VALUE}\b)", re.I)
    match = correction.search(text)
    if match:
        old, new = match["old"], match["new"]
        if not (re.fullmatch(r"[A-Za-z]+\d+", old) or re.fullmatch(r"[A-Za-z]+\d+", new)):
            normalized = text[:match.start()] + new + text[match.end():]
            normalized = re.sub(r"\s+([,?.!])", r"\1", normalized)
            normalized = re.sub(r"\s{2,}", " ", normalized).strip(" ,")
            return normalized, {"type": "explicit_value", "from": old, "to": new}

    # Speakers also put the accepted value first: "it is 7, not 6". Keep the
    # accepted value and remove only the explicit rejected alternative.
    accepted_first = re.compile(
        rf"(?P<new>\b{_CORRECTION_VALUE}\b)\s*,?\s+not\s+(?P<old>\b{_CORRECTION_VALUE}\b)", re.I)
    match = accepted_first.search(text)
    if match:
        old, new = match["old"], match["new"]
        if old.lower() != new.lower() and not (
            re.fullmatch(r"[A-Za-z]+\d+", old) or re.fullmatch(r"[A-Za-z]+\d+", new)
        ):
            normalized = text[:match.start()] + new + text[match.end():]
            normalized = re.sub(r"\s+([,?.!])", r"\1", normalized)
            normalized = re.sub(r"\s{2,}", " ", normalized).strip(" ,")
            return normalized, {"type": "accepted_value", "from": old, "to": new}
    return text, None


def normalize_disfluencies(text):
    """Remove a narrow list of speech fillers and immediate repetitions.

    This is deterministic transcript cleanup, not semantic rewriting. The raw
    text remains in telemetry and every removal is returned for inspection.
    """
    changes = []
    cleaned = text
    filler = re.compile(r"(?i)(?<!\w)(?:um+|uh+|erm+|er+|ah+)(?!\w)[,\s]*")
    for match in filler.finditer(cleaned):
        changes.append({"type": "filler", "text": match.group(0).strip(" ,")})
    cleaned = filler.sub(" ", cleaned)
    repeat = re.compile(r"(?i)\b([a-z][a-z0-9'-]{1,30})(?:\s+\1\b)+")
    while True:
        match = repeat.search(cleaned)
        if not match:
            break
        changes.append({"type": "repetition", "text": match.group(0)})
        cleaned = cleaned[:match.start()] + match.group(1) + cleaned[match.end():]
    cleaned = re.sub(r"\s+([,?.!])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,")
    return cleaned, changes


def normalize_correction(text, aliases):
    """Resolve explicit local values or a trailing unambiguous subject correction.

    Ordinary uses of 'actually' are untouched. Unknown replacements are left
    verbatim and flagged so an earlier product cannot silently win retrieval.
    """
    normalized, value_change = _normalize_explicit_value_correction(text)
    if value_change:
        return normalized, value_change, False

    match = re.search(r"[,;.!?\s]+(?:sorry[,\s]+(?:I\s+meant\s+)?|I\s+meant\s+|actually[,\s]+(?:I\s+meant\s+)?)([^,;.!?]+)[.!?\s]*$", text, re.I)
    if not match:
        return text, None, False
    prefix, replacement = text[:match.start()].rstrip(' ,;.!?'), match[1].strip()
    subjects = [a for a in aliases.values() if re.search(r'(?<!\w)' + re.escape(a) + r'(?!\w)', prefix, re.I)]
    if not subjects:
        return text, None, False
    # A short product suffix is safe only within the same product family.
    candidates = [a for a in aliases.values() if a.lower() == replacement.lower() or
                  (len(subjects) == 1 and a.rsplit(' ', 1)[0].lower() == subjects[0].rsplit(' ', 1)[0].lower()
                   and a.rsplit(' ', 1)[-1].lower() == replacement.lower())]
    explicit = bool(re.search(r"\b(?:sorry|I\s+meant)\b", match[0], re.I))
    if not explicit and not candidates and not re.fullmatch(r"[A-Za-z]+\s*\d+", replacement):
        return text, None, False
    if len(subjects) != 1 or len(candidates) != 1:
        return text, None, True
    normalized = re.sub(r'(?<!\w)' + re.escape(subjects[0]) + r'(?!\w)', candidates[0], prefix, flags=re.I)
    return normalized, {'from': subjects[0], 'to': candidates[0]}, False
