#!/usr/bin/env python3
"""Repository policy checks for CI (PLAN §8)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
FICTIONAL_MARKERS = (
    "FICTIONAL SAMPLE DATA — Alex Doe is not a real person.",
    "FICTIONAL SAMPLE DATA - Alex Doe is not a real person.",
    "FICTIONAL SAMPLE DATA for portfolio demo only.",
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b")
ALLOWED_PHONE_PREFIX = "555-01"
TRACKED_FORBIDDEN = (
    ".env",
    "var/",
    "data/",
)
TRACKED_FORBIDDEN_GLOBS = ("*.db", "*.db*", "*.sqlite3", "*.sqlite3*")
SHA_USES_RE = re.compile(r"^\s*-\s*uses:\s*([^\s#]+)", re.MULTILINE)
CHECKOUT_RE = re.compile(r"uses:\s*actions/checkout@[0-9a-f]{40}")
PERSIST_RE = re.compile(r"persist-credentials:\s*false")
PERMISSIONS_RE = re.compile(r"^permissions:\s*\{\s*contents:\s*read\s*\}", re.MULTILINE)
DOCKERIGNORE_REQUIRED = (".env*", "data/", "var/", "*.db*", "*.sqlite3*")


def _fail(msg: str) -> None:
    print(f"check_repo: {msg}", file=sys.stderr)
    sys.exit(1)


def _git_ls_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def check_fictional_markers() -> None:
    for path in SAMPLES.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".md", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if not any(m in text for m in FICTIONAL_MARKERS):
                _fail(f"missing fictional marker in {path.relative_to(ROOT)}")
        elif path.suffix.lower() == ".pdf":
            raw = path.read_bytes()
            if not any(m.encode("ascii", "ignore") in raw for m in FICTIONAL_MARKERS):
                _fail(f"missing fictional marker in PDF {path.relative_to(ROOT)}")
        elif path.suffix.lower() == ".docx":
            import zipfile

            with zipfile.ZipFile(path) as zf:
                xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
            if not any(m.replace("—", "-") in xml or m in xml for m in FICTIONAL_MARKERS):
                _fail(f"missing fictional marker in DOCX {path.relative_to(ROOT)}")


_SKIP_PHONE_SCAN_SUFFIXES = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}


def check_tracked_contact_data(files: list[str]) -> None:
    for rel in files:
        if not rel.startswith("samples/"):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        if path.suffix.lower() in _SKIP_PHONE_SCAN_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for email in EMAIL_RE.findall(text):
            if "@example.com" not in email.lower():
                _fail(f"non-example email in tracked file {rel}: {email}")
        for phone in PHONE_RE.findall(text):
            digits = re.sub(r"\D", "", phone)
            if len(digits) < 10:
                continue
            norm = phone.replace(".", "-").replace(" ", "-")
            if "555-01" in norm or "55501" in digits:
                continue
            if digits.startswith("55501"):
                continue
            _fail(f"disallowed phone in tracked file {rel}: {phone}")


def check_tracked_policy(files: list[str]) -> None:
    for rel in files:
        name = Path(rel).name
        if name.startswith(".env") and name != ".env.example":
            _fail(f"tracked env file: {rel}")
        if rel.startswith("var/") or rel.startswith("data/"):
            _fail(f"tracked data path: {rel}")
        for pat in TRACKED_FORBIDDEN_GLOBS:
            if Path(rel).match(pat):
                _fail(f"tracked db/sqlite file: {rel}")


def check_pdf_bytes() -> None:
    import importlib.util

    script = ROOT / "scripts" / "make_sample_pdf.py"
    pdf = SAMPLES / "alex-doe-certificates.pdf"
    spec = importlib.util.spec_from_file_location("make_sample_pdf", script)
    if spec is None or spec.loader is None:
        _fail("could not load make_sample_pdf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    expected = mod._PDF
    if pdf.read_bytes() != expected:
        _fail("alex-doe-certificates.pdf does not match make_sample_pdf.py output")


def check_workflows() -> None:
    wf_dir = ROOT / ".github" / "workflows"
    if not wf_dir.is_dir():
        _fail("missing .github/workflows")
    for wf in wf_dir.glob("*.yml"):
        text = wf.read_text(encoding="utf-8")
        if "uses:" in text:
            for match in SHA_USES_RE.finditer(text):
                ref = match.group(1).split("@")[-1]
                if not re.fullmatch(r"[0-9a-f]{40}", ref):
                    _fail(f"{wf.name}: uses: not pinned to 40-char SHA: {match.group(1)}")
        if "actions/checkout@" in text and not PERSIST_RE.search(text):
            _fail(f"{wf.name}: checkout missing persist-credentials: false")
    ci = wf_dir / "ci.yml"
    if ci.is_file() and not PERMISSIONS_RE.search(ci.read_text(encoding="utf-8")):
        _fail("ci.yml: expected top-level permissions: { contents: read }")


def check_dockerignore() -> None:
    di = ROOT / ".dockerignore"
    if not di.is_file():
        _fail("missing .dockerignore")
    content = di.read_text(encoding="utf-8")
    for req in DOCKERIGNORE_REQUIRED:
        if req not in content:
            _fail(f".dockerignore missing entry: {req}")


def main() -> None:
    files = _git_ls_files()
    check_fictional_markers()
    check_tracked_contact_data(files)
    check_tracked_policy(files)
    check_pdf_bytes()
    check_workflows()
    check_dockerignore()
    print("check_repo: ok")


if __name__ == "__main__":
    main()
