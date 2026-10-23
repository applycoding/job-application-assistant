"""Skill lexicon for retrieval, job parsing, and truth checks."""

from __future__ import annotations

import hashlib
import re
import tomllib
from functools import lru_cache
from importlib import resources
from pathlib import Path

CASE_SENSITIVE_SKILLS = frozenset({"Go", "R", ".NET", "Node.js"})
# Allow a sentence-ending '.' after a skill token, but not '.' continuing the token (e.g. Node.js).
_SKILL_TERM_TRAIL = r"(?![A-Za-z0-9+#])"
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.]*", re.IGNORECASE)


def count_tokens(text: str) -> int:
    return len(_TOKEN_RE.findall(text.lower()))


def _skill_rows_from_toml(data: dict[str, object]) -> list[dict[str, object]]:
    raw: object = data.get("skills", data.get("skill", []))
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    return []


def _merge_skill_maps(
    builtin: dict[str, list[str]],
    extra: dict[str, list[str]],
) -> dict[str, list[str]]:
    merged = dict(builtin)
    for name, aliases in extra.items():
        if name in merged:
            merged[name] = sorted(set(merged[name]) | set(aliases))
        else:
            merged[name] = sorted(set(aliases))
    return merged


def _canonical_payload(skills: dict[str, list[str]]) -> bytes:
    lines: list[str] = []
    for name in sorted(skills.keys(), key=str.casefold):
        aliases = skills[name]
        lines.append("[[skills]]")
        lines.append(f'name = "{name}"')
        if aliases:
            inner = ", ".join(f'"{a}"' for a in aliases)
            lines.append(f"aliases = [{inner}]")
        lines.append("")
    return "\n".join(lines).encode("utf-8")


class SkillLexicon:
    def __init__(self, skills: dict[str, list[str]], version: str) -> None:
        self._skills = skills
        self._version = version
        self._patterns: list[tuple[str, re.Pattern[str]]] = []
        for name, aliases in skills.items():
            for term in [name, *aliases]:
                if name in CASE_SENSITIVE_SKILLS:
                    pat = re.compile(rf"(?<![A-Za-z0-9+#.]){re.escape(term)}{_SKILL_TERM_TRAIL}")
                else:
                    pat = re.compile(
                        rf"(?<![a-z0-9+#.]){re.escape(term)}{_SKILL_TERM_TRAIL}",
                        re.IGNORECASE,
                    )
                self._patterns.append((name, pat))

    @property
    def version(self) -> str:
        return self._version

    @property
    def skill_names(self) -> frozenset[str]:
        return frozenset(self._skills.keys())

    @classmethod
    def load(cls, skills_file: Path | None = None) -> SkillLexicon:
        return load_lexicon(skills_file)

    def find(self, text: str) -> set[str]:
        found: set[str] = set()
        for name, pat in self._patterns:
            if pat.search(text):
                found.add(name)
        return found

    def skills_in_text_ordered(self, text: str) -> list[str]:
        return sorted(self.find(text), key=str.casefold)

    def aliases_for(self, skill: str) -> list[str]:
        return list(self._skills.get(skill, []))


def _load_toml_skills(path: Path) -> dict[str, list[str]]:
    data = tomllib.loads(path.read_bytes().decode("utf-8"))
    out: dict[str, list[str]] = {}
    for entry in _skill_rows_from_toml(data):
        name = str(entry["name"]).strip()
        aliases_raw = entry.get("aliases", [])
        if isinstance(aliases_raw, str):
            aliases_list: list[object] = [aliases_raw]
        elif isinstance(aliases_raw, list):
            aliases_list = aliases_raw
        else:
            aliases_list = []
        out[name] = [str(a).strip() for a in aliases_list if str(a).strip()]
    return out


def load_lexicon(skills_file: Path | None = None) -> SkillLexicon:
    builtin_path = Path(
        str(resources.files("jaa.resources").joinpath("skills.toml")),
    )
    builtin = _load_toml_skills(builtin_path)
    extra: dict[str, list[str]] = {}
    if skills_file is not None and skills_file.is_file():
        extra = _load_toml_skills(skills_file)
    merged = _merge_skill_maps(builtin, extra)
    version = hashlib.sha256(_canonical_payload(merged)).hexdigest()[:16]
    return SkillLexicon(merged, version)


@lru_cache(maxsize=1)
def default_lexicon() -> SkillLexicon:
    return load_lexicon()
