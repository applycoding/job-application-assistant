"""Server-rendered HTML routes (POST-redirect-GET)."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from jaa import __version__
from jaa.generation.pipeline import create_run, is_stale, prune_run
from jaa.ingest.loaders import (
    IngestError,
    UploadTooLarge,
    detect_media_type,
    load_lines,
    read_upload_limited,
)
from jaa.jobs.parser import JobParseError, parse_job
from jaa.limits import MAX_JOB_CHARS
from jaa.models import RunOptions
from jaa.privacy.outbound import build_outbound_draft
from jaa.providers.base import ProviderError
from jaa.retrieval.service import retrieve_for_job
from jaa.samples import load_samples
from jaa.storage.repo import DuplicateDocument
from jaa.web.deps import (
    ClockDep,
    CsrfTokenDep,
    LexiconDep,
    MutationAuth,
    PipelineDeps,
    RepoDep,
    SettingsDep,
)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter()


def _redirect(path: str, status_code: int = 303) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=status_code)


def _reference_date(settings: SettingsDep, clock: ClockDep) -> date:
    if settings.reference_date is not None:
        return settings.reference_date
    return clock.now().date()


@router.get("/")
def index(
    request: Request,
    repo: RepoDep,
    settings: SettingsDep,
    csrf_token: CsrfTokenDep,
) -> object:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "documents": repo.list_documents(),
            "jobs": repo.list_jobs(),
            "csrf_token": csrf_token,
            "provider": settings.provider,
            "enable_samples": settings.enable_samples,
            "version": __version__,
        },
    )


@router.post("/samples/load")
async def html_load_samples(
    _auth: MutationAuth,
    repo: RepoDep,
    settings: SettingsDep,
    lexicon: LexiconDep,
    clock: ClockDep,
) -> RedirectResponse:
    if not settings.enable_samples:
        raise HTTPException(status_code=404, detail="Samples disabled")
    load_samples(repo, settings, lexicon, clock)
    return _redirect("/")


@router.post("/documents")
async def html_upload_document(
    _auth: MutationAuth,
    repo: RepoDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
) -> RedirectResponse:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    try:
        data = await read_upload_limited(file, max_bytes)
    except UploadTooLarge:
        raise HTTPException(status_code=413, detail="Upload too large") from None
    filename = file.filename or "upload"
    head = data[:8192]
    try:
        media_type = detect_media_type(filename, head)
    except IngestError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    try:
        lines, warnings = load_lines(data, media_type)
    except IngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    sha = hashlib.sha256(data).hexdigest()
    try:
        doc = repo.upsert_document(filename, media_type, sha, lines, warnings)
    except DuplicateDocument as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _redirect(f"/documents/{doc.id}")


@router.get("/documents/{doc_id}")
def document_page(
    request: Request,
    doc_id: str,
    repo: RepoDep,
    csrf_token: CsrfTokenDep,
) -> object:
    doc = next((d for d in repo.list_documents() if d.id == doc_id), None)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = repo.get_chunks(doc_id)
    visible = [c for c in chunks if c.kind not in ("contact",)]
    return templates.TemplateResponse(
        request,
        "document.html",
        {
            "document": doc,
            "chunks": visible,
            "csrf_token": csrf_token,
        },
    )


@router.post("/documents/{doc_id}/delete")
def html_delete_document(
    doc_id: str,
    _auth: MutationAuth,
    repo: RepoDep,
    delete_runs: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    also_delete_runs = delete_runs is not None and delete_runs.lower() in (
        "true",
        "on",
        "1",
        "yes",
    )
    try:
        repo.delete_document(doc_id, delete_runs=also_delete_runs)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found") from None
    return _redirect("/")


@router.post("/jobs")
def html_create_job(
    _auth: MutationAuth,
    repo: RepoDep,
    lexicon: LexiconDep,
    clock: ClockDep,
    text: Annotated[str, Form()],
) -> RedirectResponse:
    if not text.strip() or len(text) > MAX_JOB_CHARS:
        raise HTTPException(status_code=422, detail="Invalid job post text")
    try:
        job = parse_job(text, lexicon, clock)
    except JobParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = repo.save_job(job)
    return _redirect(f"/jobs/{job.id}")


@router.get("/jobs/{job_id}")
def job_page(
    request: Request,
    job_id: str,
    repo: RepoDep,
    settings: SettingsDep,
    lexicon: LexiconDep,
    clock: ClockDep,
    csrf_token: CsrfTokenDep,
) -> object:
    try:
        job = repo.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    outbound_preview: str | None = None
    if settings.provider != "mock":
        ref = _reference_date(settings, clock)
        try:
            _version, chunks = repo.corpus_snapshot(ref)
            if chunks:
                result = retrieve_for_job(job, chunks, lexicon)
                draft = build_outbound_draft(job, result)
                outbound_preview = draft.model_dump_json(indent=2)
        except ValueError:
            outbound_preview = None
    runs = repo.list_runs(job_id)
    return templates.TemplateResponse(
        request,
        "job.html",
        {
            "job": job,
            "runs": runs,
            "csrf_token": csrf_token,
            "provider": settings.provider,
            "judge_default": settings.judge,
            "outbound_preview": outbound_preview,
        },
    )


@router.post("/jobs/{job_id}/runs")
async def html_create_run(
    job_id: str,
    _auth: MutationAuth,
    deps: PipelineDeps,
    settings: SettingsDep,
    judge: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    judge_on = settings.judge
    if judge is not None:
        judge_on = judge.lower() in ("on", "true", "1", "yes")
    options = RunOptions(judge=judge_on)
    try:
        run = await create_run(deps, job_id, options)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Run deadline exceeded") from None
    return _redirect(f"/runs/{run.id}")


@router.get("/runs/{run_id}")
def run_page(
    request: Request,
    run_id: str,
    repo: RepoDep,
    settings: SettingsDep,
    clock: ClockDep,
    csrf_token: CsrfTokenDep,
) -> object:
    try:
        run = repo.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    ref = _reference_date(settings, clock)
    current_version, _chunks = repo.corpus_snapshot(ref)
    stale = is_stale(run, current_version)
    return templates.TemplateResponse(
        request,
        "run.html",
        {
            "run": run,
            "stale": stale,
            "csrf_token": csrf_token,
            "report": run.report,
        },
    )


@router.post("/runs/{run_id}/prune")
async def html_prune_run(
    run_id: str,
    _auth: MutationAuth,
    deps: PipelineDeps,
) -> RedirectResponse:
    try:
        child = await prune_run(deps, run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    return _redirect(f"/runs/{child.id}")


@router.post("/data/delete")
def html_delete_all(_auth: MutationAuth, repo: RepoDep) -> RedirectResponse:
    repo.delete_all()
    return _redirect("/")
