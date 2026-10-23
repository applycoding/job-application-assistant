"""JSON API routes (§5.10)."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from jaa.export import export_json, export_markdown
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
from jaa.models import Document, JobPost, Run, RunOptions
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

router = APIRouter(prefix="/api")


class CreateJobRequest(BaseModel):
    text: str
    extra_questions: list[str] = Field(default_factory=list)


@router.get("/csrf")
def api_csrf(token: CsrfTokenDep) -> dict[str, str]:
    return {"token": token}


@router.post("/documents", status_code=201, response_model=Document)
async def api_upload_document(
    _auth: MutationAuth,
    repo: RepoDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
) -> Document:
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
        return repo.upsert_document(filename, media_type, sha, lines, warnings)
    except DuplicateDocument as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/documents", response_model=list[Document])
def api_list_documents(repo: RepoDep) -> list[Document]:
    return repo.list_documents()


@router.get("/documents/{doc_id}/chunks")
def api_document_chunks(doc_id: str, repo: RepoDep) -> list[dict[str, Any]]:
    if not any(d.id == doc_id for d in repo.list_documents()):
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = repo.get_chunks(doc_id)
    return [c.model_dump() for c in chunks]


@router.delete("/documents/{doc_id}")
def api_delete_document(
    doc_id: str,
    _auth: MutationAuth,
    repo: RepoDep,
    delete_runs: bool = Query(default=False),
) -> dict[str, int]:
    try:
        deleted = repo.delete_document(doc_id, delete_runs=delete_runs)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found") from None
    return {"deleted_runs": deleted}


@router.post("/jobs", status_code=201, response_model=JobPost)
def api_create_job(
    body: CreateJobRequest,
    _auth: MutationAuth,
    repo: RepoDep,
    lexicon: LexiconDep,
    clock: ClockDep,
) -> JobPost:
    text = body.text
    if not text.strip() or len(text) > MAX_JOB_CHARS:
        raise HTTPException(status_code=422, detail="Invalid job post text")
    try:
        job = parse_job(text, lexicon, clock, extra_questions=body.extra_questions)
    except JobParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return repo.save_job(job)


@router.get("/jobs/{job_id}", response_model=JobPost)
def api_get_job(job_id: str, repo: RepoDep) -> JobPost:
    try:
        return repo.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None


@router.get("/jobs/{job_id}/outbound-preview")
def api_outbound_preview(
    job_id: str,
    repo: RepoDep,
    lexicon: LexiconDep,
    settings: SettingsDep,
    clock: ClockDep,
) -> dict[str, Any]:
    try:
        job = repo.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    ref = settings.reference_date or clock.now().date()
    try:
        _version, chunks = repo.corpus_snapshot(ref)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not chunks:
        raise HTTPException(status_code=409, detail="upload documents first")
    result = retrieve_for_job(job, chunks, lexicon)
    draft = build_outbound_draft(job, result)
    return json.loads(draft.model_dump_json())  # type: ignore[no-any-return]


@router.post("/jobs/{job_id}/runs", status_code=201)
async def api_create_run(
    job_id: str,
    _auth: MutationAuth,
    deps: PipelineDeps,
    opts: RunOptions = RunOptions(),
) -> Run:
    options = opts
    try:
        return await create_run(deps, job_id, options)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Run deadline exceeded") from None


@router.get("/runs/{run_id}")
def api_get_run(
    run_id: str,
    repo: RepoDep,
    settings: SettingsDep,
    clock: ClockDep,
) -> dict[str, Any]:
    try:
        run = repo.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    ref = settings.reference_date or clock.now().date()
    current_version, _chunks = repo.corpus_snapshot(ref)
    payload = run.model_dump()
    payload["stale"] = is_stale(run, current_version)
    return payload


@router.post("/runs/{run_id}/prune", status_code=201, response_model=Run)
async def api_prune_run(
    run_id: str,
    _auth: MutationAuth,
    deps: PipelineDeps,
) -> Run:
    try:
        return await prune_run(deps, run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@router.get("/runs/{run_id}/export")
def api_export_run(
    run_id: str,
    repo: RepoDep,
    format: Literal["md", "json"] = Query(default="md"),
    citations: bool = Query(default=True),
) -> Response:
    try:
        run = repo.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    if format not in ("md", "json"):
        raise HTTPException(status_code=422, detail="Invalid format")
    if format == "md":
        body = export_markdown(run, citations=citations)
        media = "text/markdown; charset=utf-8"
        filename = f"{run_id}.md"
    else:
        body = export_json(run)
        media = "application/json; charset=utf-8"
        filename = f"{run_id}.json"
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/samples/load")
def api_load_samples(
    _auth: MutationAuth,
    repo: RepoDep,
    settings: SettingsDep,
    lexicon: LexiconDep,
    clock: ClockDep,
) -> dict[str, str]:
    if not settings.enable_samples:
        raise HTTPException(status_code=404, detail="Samples disabled")
    try:
        load_samples(repo, settings, lexicon, clock)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.delete("/data", status_code=204)
def api_delete_data(_auth: MutationAuth, repo: RepoDep) -> Response:
    repo.delete_all()
    return Response(status_code=204)
