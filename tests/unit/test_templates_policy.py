from pathlib import Path


def test_no_unsafe_jinja() -> None:
    root = Path("src/jaa/web")
    for path in list(root.rglob("*.html")) + list(root.rglob("*.js")):
        text = path.read_text(encoding="utf-8")
        assert "|safe" not in text
        assert "Markup(" not in text
        if path.suffix == ".js":
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("*"):
                    continue
                assert "innerHTML" not in line
        else:
            assert "innerHTML" not in text
