import tomllib
from pathlib import Path

ALLOWLIST = {
    Path("src/jaa/providers/mock.py"),
}


def test_no_model_ids_in_src() -> None:
    toml = tomllib.loads(Path("src/jaa/resources/providers.toml").read_text(encoding="utf-8"))
    models: set[str] = set()
    for cfg in toml.values():
        if isinstance(cfg, dict):
            for k in ("model", "judge_model"):
                if k in cfg:
                    models.add(cfg[k])
    for path in Path("src").rglob("*.py"):
        if path in ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        for m in models:
            if m.startswith("mock-"):
                continue
            assert m not in text, f"{m} found in {path}"
