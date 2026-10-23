"""Shared Pydantic models (PLAN §5.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

ChunkKind = Literal["heading", "bullet", "line", "table_row", "contact"]
MediaType = Literal["md", "txt", "pdf", "docx"]
SentenceKind = Literal["claim", "framing"]
ClaimStatus = Literal["checks_passed", "entailed", "unsupported", "not_verified"]
CheckName = Literal[
    "no_citation",
    "invalid_citation",
    "number",
    "year",
    "duration",
    "employer",
    "skill",
    "skill_version",
    "ownership",
    "negation",
    "mixed_citations",
    "judge",
]


class RawLine(BaseModel):
    line_no: int
    text: str
    kind: ChunkKind
    section: list[str]


class Chunk(BaseModel):
    id: str
    doc_id: str
    line_no: int
    kind: ChunkKind
    text: str
    section: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def evidence_text(self) -> str:
        return f"{self.section}\n{self.text}"


class Document(BaseModel):
    id: str
    filename: str
    filename_key: str
    media_type: MediaType
    sha256: str
    chunk_count: int
    created_at: datetime
    warnings: list[str] = []


class Requirement(BaseModel):
    id: str
    text: str
    priority: Literal["must", "nice"]
    skills: list[str]
    terms: list[str]
    min_years: int | None = None


class Question(BaseModel):
    id: str
    text: str = Field(max_length=500)


class JobPost(BaseModel):
    id: str
    title: str
    company: str | None
    text: str
    requirements: list[Requirement]
    questions: list[Question]
    warnings: list[str] = []
    created_at: datetime


class EvidenceItem(BaseModel):
    chunk: Chunk
    score: float
    requirement_ids: list[str]
    matched_terms: list[str]


class Gap(BaseModel):
    requirement_id: str
    term: str | None


class RetrievalResult(BaseModel):
    evidence: list[EvidenceItem]
    gaps: list[Gap]


class SentenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=400)
    citations: list[str] = Field(max_length=4)
    requirement_ids: list[str] = Field(max_length=5)
    rationale: str = Field(max_length=300)


class AnswerOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    sentences: list[SentenceOut] = Field(min_length=1, max_length=5)


class LLMDraftOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[AnswerOut] = Field(min_length=1, max_length=10)
    cover_note: list[SentenceOut] = Field(min_length=1, max_length=6)


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentence_id: str
    entailed: bool
    rationale: str = Field(max_length=300)


class JudgeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdicts: list[JudgeVerdict] = Field(max_length=60)


class MatchedTerm(BaseModel):
    chunk_id: str
    terms: list[str]


class Explanation(BaseModel):
    requirement_ids: list[str]
    matches: list[MatchedTerm]
    model_rationale: str


class Sentence(BaseModel):
    id: str
    kind: SentenceKind
    text: str
    citations: list[str] = []
    requirement_ids: list[str] = []
    rationale: str = ""
    template_id: str | None = None
    explanation: Explanation | None = None


class AnswerDraft(BaseModel):
    question_id: str
    question: str
    sentences: list[Sentence]


class CoverNote(BaseModel):
    salutation: str
    sentences: list[Sentence]
    signoff: str = "Kind regards,"


class Drafts(BaseModel):
    answers: list[AnswerDraft]
    cover_note: CoverNote


class CheckFailure(BaseModel):
    check: CheckName
    token: str | None
    detail: str
    outcome: Literal["fail", "abstain"]


class SentenceCheck(BaseModel):
    sentence_id: str
    status: ClaimStatus
    failures: list[CheckFailure]
    checks_run: list[CheckName]
    judge: JudgeVerdict | None = None


class TruthReport(BaseModel):
    sentences: list[SentenceCheck]
    judge_enabled: bool

    @computed_field  # type: ignore[prop-decorator]
    @property
    def claims(self) -> int:
        return sum(1 for s in self.sentences if _is_claim_sentence_id(s.sentence_id))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def unsupported(self) -> int:
        return sum(
            1
            for s in self.sentences
            if _is_claim_sentence_id(s.sentence_id) and s.status == "unsupported"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def not_verified(self) -> int:
        return sum(
            1
            for s in self.sentences
            if _is_claim_sentence_id(s.sentence_id) and s.status == "not_verified"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def flagged_ids(self) -> list[str]:
        return [
            s.sentence_id
            for s in self.sentences
            if _is_claim_sentence_id(s.sentence_id)
            and s.status in ("unsupported", "not_verified")
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def badge_text(self) -> str:
        n = self.claims
        flagged = self.unsupported + self.not_verified
        if flagged == 0 and not self.judge_enabled:
            return "No deterministic issues found"
        if flagged == 0 and self.judge_enabled:
            return f"No deterministic issues found; judge agreed on all {n} claims"
        return f"{self.unsupported} unsupported, {self.not_verified} not verified (of {n} claims)"


def _is_claim_sentence_id(sentence_id: str) -> bool:
    if sentence_id.startswith("C.F"):
        return False
    if sentence_id.startswith("C.S"):
        return True
    return sentence_id.startswith("Q") and ".S" in sentence_id


class RunOptions(BaseModel):
    judge: bool | None = None


class Run(BaseModel):
    id: str
    job_id: str
    parent_run_id: str | None
    created_at: datetime
    provider: str
    model: str
    judge_model: str | None
    judge_enabled: bool
    corpus_version: str
    check_rules_version: str
    requirements: list[Requirement]
    evidence: list[EvidenceItem]
    gaps: list[Gap]
    drafts: Drafts
    report: TruthReport
    warnings: list[str]
