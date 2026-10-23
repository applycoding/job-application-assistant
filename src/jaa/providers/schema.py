"""Portable JSON Schema subset for provider structured output."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_STRIP_KEYS = frozenset(
    {
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "pattern",
    }
)


def portable_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    return _normalize(raw)


def _normalize(node: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _STRIP_KEYS or key in ("$defs", "$schema", "title", "description"):
            continue
        if key == "properties" and isinstance(value, dict):
            props = {k: _normalize_item(v) for k, v in value.items()}
            out["properties"] = props
            out["required"] = list(props.keys())
            out["additionalProperties"] = False
        elif key == "items" and isinstance(value, dict):
            out["items"] = _normalize_item(value)
        elif key == "anyOf" and isinstance(value, list):
            out["type"] = _nullable_type(value)
        elif isinstance(value, dict):
            out[key] = _normalize_item(value)
        else:
            out[key] = value
    if "type" not in out and "properties" in out:
        out["type"] = "object"
    return out


def _normalize_item(node: Any) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if ref.startswith("#/$defs/"):
                return {"type": "object", "additionalProperties": False}
        return _normalize(node)
    return node


def _nullable_type(any_of: list[dict[str, Any]]) -> str:
    types = [item.get("type") for item in any_of if item.get("type") != "null"]
    if len(types) == 1 and isinstance(types[0], str):
        return types[0]
    return "string"
