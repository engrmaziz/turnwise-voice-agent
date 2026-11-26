"""Template catalog keyed by FSM action. Missing keys fail at load."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from dialogue.actions import ACTIONS

CATALOG_PATH = Path(__file__).resolve().parent / "templates.toml"
_DEFAULT: TemplateCatalog | None = None


class Template(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str
    id: str
    text: str
    ask: str = ""


class TemplateCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    by_action: dict[str, Template]
    by_id: dict[str, str]
    warmup: dict[str, str] = Field(default_factory=dict)

    def require_action(self, action: str) -> Template:
        found = self.by_action.get(action)
        if found is None:
            raise ValueError(f"unknown template {action}")
        return found

    def text_for_id(self, template_id: str, fallback: str) -> str:
        if template_id in self.by_id:
            return self.by_id[template_id]
        if template_id in self.warmup:
            return self.warmup[template_id]
        return fallback


def load_templates(path: Path | None = None) -> TemplateCatalog:
    global _DEFAULT
    if path is None and _DEFAULT is not None:
        return _DEFAULT
    target = path if path is not None else CATALOG_PATH
    payload = tomllib.loads(target.read_text(encoding="utf-8"))
    warmup_raw = payload.pop("warmup", {})
    warmup = (
        {str(key): str(value) for key, value in warmup_raw.items()}
        if isinstance(warmup_raw, dict)
        else {}
    )
    by_action: dict[str, Template] = {}
    by_id: dict[str, str] = dict(warmup)
    for action, raw in payload.items():
        if not isinstance(raw, dict):
            raise ValueError(f"template {action} must be a table")
        tmpl = Template(
            action=action,
            id=str(raw.get("id", action)),
            text=str(raw["text"]),
            ask=str(raw.get("ask", "")),
        )
        by_action[action] = tmpl
        by_id[tmpl.id] = tmpl.text
    missing = sorted(set(ACTIONS) - set(by_action))
    if missing:
        raise ValueError(f"missing template for {missing[0]}")
    extra = sorted(set(by_action) - set(ACTIONS))
    if extra:
        raise ValueError(f"unknown template {extra[0]}")
    catalog = TemplateCatalog(by_action=by_action, by_id=by_id, warmup=warmup)
    if path is None:
        _DEFAULT = catalog
    return catalog
