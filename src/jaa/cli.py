"""Command-line interface: serve, seed, ingest, reset."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import uvicorn

from jaa.clock import SystemClock
from jaa.config import Settings
from jaa.ids import Uuid4Factory
from jaa.ingest.loaders import detect_media_type, load_lines
from jaa.storage.db import create_db_engine
from jaa.storage.repo import DuplicateDocument, Repository
from jaa.samples import load_samples
from jaa.truth.lexicon import SkillLexicon


def _build_repo(settings: Settings) -> Repository:
    engine = create_db_engine(settings.db_path)
    lexicon = SkillLexicon.load(settings.skills_file)
    return Repository(engine, SystemClock(), Uuid4Factory(), lexicon)


def cmd_serve(settings: Settings) -> None:
    from jaa.app import create_app

    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, workers=1)


def cmd_seed(settings: Settings) -> None:
    repo = _build_repo(settings)
    lexicon = SkillLexicon.load(settings.skills_file)
    clock = SystemClock()
    load_samples(repo, settings, lexicon, clock)


def cmd_ingest(settings: Settings, path: Path) -> None:
    if not path.is_file():
        print(f"Not a file: {path}", file=sys.stderr)
        raise SystemExit(1)
    data = path.read_bytes()
    head = data[:8192]
    media_type = detect_media_type(path.name, head)
    lines, warnings = load_lines(data, media_type)
    sha = hashlib.sha256(data).hexdigest()
    repo = _build_repo(settings)
    try:
        doc = repo.upsert_document(path.name, media_type, sha, lines, warnings)
    except DuplicateDocument as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Ingested {doc.filename} as {doc.id} ({doc.chunk_count} chunks)")


def cmd_reset(settings: Settings) -> None:
    repo = _build_repo(settings)
    repo.delete_all()
    print("Database reset.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="jaa", description="Job Application Assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="Run the web server")

    sub.add_parser("seed", help="Load sample CV and job posts")

    ingest_p = sub.add_parser("ingest", help="Ingest a single document file")
    ingest_p.add_argument("path", type=Path, help="Path to .md, .txt, .pdf, or .docx")

    sub.add_parser("reset", help="Delete all stored data")

    args = parser.parse_args(argv)
    settings = Settings.from_env()

    if args.command == "serve":
        cmd_serve(settings)
    elif args.command == "seed":
        cmd_seed(settings)
    elif args.command == "ingest":
        cmd_ingest(settings, args.path)
    elif args.command == "reset":
        cmd_reset(settings)
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
