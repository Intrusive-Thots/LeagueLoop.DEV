"""
Parse a champion list pasted from somewhere else.

People keep their ARAM order in a Discord message, a spreadsheet, a note, or
a tier-list site. Retyping sixty champions into a UI one click at a time is
the kind of chore that makes a feature go unused, so accept the text as it
comes.

Deliberately forgiving about *format* and strict about *identity*: any
sensible separator works and punctuation is ignored, but a name that does not
resolve to a real champion is reported rather than silently dropped — a list
that quietly lost four entries is worse than one that refuses to import.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

#: Anything people plausibly separate champion names with.
_SEPARATORS = re.compile(r"[,\n\r\t;|/]+")
#: Leading list decoration: "1.", "12)", "- ", "* ", "#3", "•".
_LEADING_ORDINAL = re.compile(
    r"^\s*(?:[#\-*•>]\s*)?(?:\d{1,3}\s*[.)\]:-]?)?\s*"
)
#: Annotations people leave behind: "(52.1%)", "[S tier]". Removed before
#: splitting, so a bracket inside an annotation is never mistaken for the
#: wrapper around the whole list.
_ANNOTATION = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")


def _normalise(name: str) -> str:
    """Lowercase, strip punctuation and spaces: "Cho'Gath" -> "chogath"."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


@dataclass
class ImportResult:
    """What a paste produced, including what it could not resolve."""

    champion_ids: List[int] = field(default_factory=list)
    resolved_names: List[str] = field(default_factory=list)
    unknown: List[str] = field(default_factory=list)
    duplicates: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.champion_ids)

    @property
    def summary(self) -> str:
        """One sentence for the UI, naming every problem it found."""
        if not self.champion_ids and not self.unknown:
            return "Nothing to import — the clipboard had no champion names."

        parts = [
            "{} champion{}".format(
                len(self.champion_ids), "" if len(self.champion_ids) == 1 else "s"
            )
        ]
        if self.duplicates:
            parts.append(
                "{} duplicate{} removed".format(
                    len(self.duplicates), "" if len(self.duplicates) == 1 else "s"
                )
            )
        if self.unknown:
            shown = ", ".join(self.unknown[:3])
            more = (
                " and {} more".format(len(self.unknown) - 3)
                if len(self.unknown) > 3 else ""
            )
            parts.append("{} not recognised ({}{})".format(len(self.unknown), shown, more))
        return " · ".join(parts)


def split_names(text: str) -> List[str]:
    """
    Break pasted text into candidate names.

    Handles `{A, B, C}`, newline-separated lists, numbered lists and the
    trailing annotations tier-list sites leave behind. Space-separated is
    *not* treated as a separator: "Lee Sin" and "Master Yi" contain spaces,
    and guessing there loses more than it gains.
    """
    if not text:
        return []

    # Order matters. Annotations go first, so a bracket inside "[S tier]" is
    # never mistaken for the wrapper around the whole list; the wrapper goes
    # second; splitting last.
    text = _ANNOTATION.sub("", text.strip()).strip()

    if text[:1] in "{[(":
        text = text[1:]
    if text[-1:] in "}])":
        text = text[:-1]

    out = []
    for chunk in _SEPARATORS.split(text):
        chunk = chunk.strip().strip('"').strip("'").strip()
        chunk = _LEADING_ORDINAL.sub("", chunk)
        chunk = _ANNOTATION.sub("", chunk).strip()
        if chunk:
            out.append(chunk)
    return out


def build_lookup(assets: Any) -> Dict[str, int]:
    """
    Normalised champion name -> id, from AssetManager.

    Accepts both the Data Dragon key ("MonkeyKing") and the display name
    ("Wukong"), because pasted lists use either.
    """
    lookup: Dict[str, int] = {}
    data = getattr(assets, "champ_data", None) or {}
    for key, info in data.items():
        try:
            cid = int(info.get("key", 0))
        except (TypeError, ValueError):
            continue
        if cid <= 0:
            continue
        lookup[_normalise(key)] = cid
        lookup[_normalise(info.get("name", ""))] = cid

    # Fall back to whatever name map the asset manager already built.
    existing = getattr(assets, "name_to_id", None)
    if isinstance(existing, dict):
        for name, cid in existing.items():
            try:
                lookup.setdefault(_normalise(name), int(cid))
            except (TypeError, ValueError):
                continue
    lookup.pop("", None)
    return lookup


def parse_champion_list(
    text: str,
    assets: Any = None,
    lookup: Optional[Dict[str, int]] = None,
    existing: Optional[Sequence[int]] = None,
) -> ImportResult:
    """
    Turn pasted text into champion ids, preserving the pasted order.

    `existing` lets a caller treat already-present ids as duplicates, so
    appending to a list does not double entries.
    """
    if lookup is None:
        lookup = build_lookup(assets)

    result = ImportResult()
    seen = {int(c) for c in (existing or [])}

    for raw in split_names(text):
        cid = lookup.get(_normalise(raw))
        if not cid:
            result.unknown.append(raw)
            continue
        if cid in seen:
            result.duplicates.append(raw)
            continue
        seen.add(cid)
        result.champion_ids.append(cid)
        result.resolved_names.append(raw)

    return result
