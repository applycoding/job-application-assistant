"""Load committed fictional sample documents (and jobs when parser is available)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from jaa.clock import Clock
from jaa.config import Settings
from jaa.ids import IdFactory
from jaa.ingest.loaders import detect_media_type, load_lines
from jaa.jobs.parser import parse_job
from jaa.models import Document, JobPost
from jaa.storage.repo import Repository
from jaa.truth.lexicon import SkillLexicon, load_lexicon

FICTIONAL_MARKER = "FICTIONAL SAMPLE DATA - Alex Doe is not a real person."

SAMPLE_DOCUMENTS: tuple[str, ...] = (
    "alex-doe-cv.md",
    "alex-doe-projects.txt",
    "alex-doe-certificates.pdf",
    "alex-doe-volunteering.docx",
)

SAMPLE_JOBS: tuple[str, ...] = (
    "jobs/01-senior-data-engineer-acme-logistics.md",
    "jobs/02-ml-platform-engineer-globex-energy.md",
    "jobs/03-backend-python-developer-vandelay-health.md",
)


@dataclass
class SeedResult:
    documents: list[Document]
    jobs: list[JobPost]


def samples_dir(settings: Settings) -> Path:
    return settings.samples_dir


def ingest_sample_path(
    repo: Repository,
    path: Path,
    *,
    filename: str | None = None,
) -> Document:
    data = path.read_bytes()
    name = filename or path.name
    digest = hashlib.sha256(data).hexdigest()
    head = data[:16] if len(data) >= 16 else data
    media_type = detect_media_type(name, head)
    lines, warnings = load_lines(data, media_type)
    return repo.upsert_document(name, media_type, digest, lines, warnings)


def seed_documents(repo: Repository, settings: Settings) -> list[Document]:
    root = samples_dir(settings)
    docs: list[Document] = []
    for rel in SAMPLE_DOCUMENTS:
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(f"Missing sample file: {path}")
        docs.append(ingest_sample_path(repo, path))
    return docs


def seed_jobs(
    repo: Repository,
    settings: Settings,
    clock: Clock,
    lexicon: SkillLexicon,
) -> list[JobPost]:
    root = samples_dir(settings)
    saved: list[JobPost] = []
    for rel in SAMPLE_JOBS:
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(f"Missing sample job: {path}")
        text = path.read_text(encoding="utf-8")
        job = parse_job(text, lexicon, clock)
        saved.append(repo.save_job(job))
    return saved


def seed(
    repo: Repository,
    settings: Settings,
    clock: Clock,
    ids: IdFactory,
    lexicon: SkillLexicon | None = None,
) -> SeedResult:
    if not settings.enable_samples:
        raise RuntimeError("Sample seeding is disabled (JAA_ENABLE_SAMPLES)")
    lex = lexicon or load_lexicon(settings.skills_file)
    documents = seed_documents(repo, settings)
    jobs = seed_jobs(repo, settings, clock, lex)
    return SeedResult(documents=documents, jobs=jobs)


def load_samples(
    repo: Repository,
    settings: Settings,
    lexicon: SkillLexicon,
    clock: Clock,
) -> SeedResult:
    """Load committed sample documents and jobs (API/CLI entry point)."""
    if not settings.enable_samples:
        raise FileNotFoundError("Sample loading is disabled")
    documents = seed_documents(repo, settings)
    jobs = seed_jobs(repo, settings, clock, lexicon)
    return SeedResult(documents=documents, jobs=jobs)
