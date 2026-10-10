"""Deterministic inference from explicit qualification text; no database access."""

import re
from collections.abc import Mapping


ALIASES = {
    "Python": ("python",),
    "SQL": ("sql", "postgresql", "mysql"),
    "Statistics": ("statistics", "statistical analysis", "statistical inference"),
    "Machine Learning Fundamentals": ("machine learning", "ML"),
    "Pandas/Data Handling": ("pandas",),
    "Git": ("git", "git version control"),
    "Data Structures & Algorithms": ("data structures", "data structures and algorithms", "DSA"),
    "Object-Oriented Programming": ("object-oriented programming", "object oriented programming", "OOP"),
    "Excel": ("microsoft excel", "excel"),
    "Data Visualization": ("data visualization", "data visualisation"),
}
_PATTERNS = {
    name: [re.compile(r"(?<!\w)" + re.escape(alias).replace(r"\ ", r"\s+") + r"(?!\w)",
                      0 if alias == "ML" else re.I) for alias in aliases]
    for name, aliases in ALIASES.items()
}
_OPTIONAL = re.compile(r"\b(?:preferred|optional|nice[ -]to[ -]have|bonus)\b", re.I)
_REQUIRED = re.compile(r"\b(?:required|requirements?|essential|mandatory|must(?:[ -]have)?|qualifications?)\b", re.I)
_NEGATED = re.compile(
    r"\b(?:not|never|isn't|aren't)\s+(?:strictly\s+)?(?:required|essential|mandatory|necessary)\b"
    r"|\bno\b[^.;]*\b(?:required|necessary)\b"
    r"|\b(?:do(?:es)?\s+not|don't|doesn't)\s+(?:need|require)\b", re.I,
)
_HEADING = re.compile(r"^\s*([\w /&-]{2,60}):\s*(.*)$")


def infer_skill_mappings(mapping_text: list[dict]) -> list[dict]:
    """Return canonical names, baseline levels and explicit requirement flags.

    Level 1 is an inferred MVP baseline, NOT employer-verified proficiency.
    No role title, user profile, seniority, career or band affects this rule.
    Unclassified mentions are omitted; an explicit requirement wins over an
    optional mention. Negation is scoped to a comma/but-separated clause.
    """
    found = {}
    for part in mapping_text:
        if not isinstance(part, Mapping) or not isinstance(part.get("text"), str):
            continue
        section = part.get("context", "ambiguous")
        if section not in {"required", "optional"}:
            section = "ambiguous"
        for line in part["text"].splitlines():
            heading = _HEADING.match(line)
            if heading:
                label, line = heading.groups()
                # Only short, skill-free heading labels establish a section.
                if not any(pattern.search(label) for patterns in _PATTERNS.values() for pattern in patterns):
                    section = ("optional" if _OPTIONAL.search(label) else "ambiguous" if _NEGATED.search(label)
                               else "required" if _REQUIRED.search(label) else "ambiguous")
            elif not any(pattern.search(line) for patterns in _PATTERNS.values() for pattern in patterns):
                if _OPTIONAL.fullmatch(line.strip()):
                    section = "optional"
                elif _REQUIRED.fullmatch(line.strip()):
                    section = "required"
                elif line.strip():
                    section = "ambiguous"
            for sentence in re.split(r"[.;!?]+", line):
                context = section
                for clause in re.split(r",|\bbut\b", sentence, flags=re.I):
                    optional = _OPTIONAL.search(clause)
                    negated = _NEGATED.search(clause)
                    required = _REQUIRED.search(clause) if not negated else None
                    local = "optional" if optional else "required" if required else context
                    if negated and not optional:
                        continue
                    # Prefix cues can govern a comma-separated skill list.
                    cue = optional or required
                    if cue and cue.start() == len(clause) - len(clause.lstrip()):
                        context = local
                    if local not in {"required", "optional"}:
                        continue
                    for name, patterns in _PATTERNS.items():
                        if any(
                            not re.search(r"\b(?:not|no|without|excluding)\s+$", clause[:match.start()], re.I)
                            for pattern in patterns for match in pattern.finditer(clause)
                        ):
                            found[name] = found.get(name, False) or local == "required"
    return [{"skill_name": name, "required_level": 1, "is_required": found[name]}
            for name in ALIASES if name in found]
