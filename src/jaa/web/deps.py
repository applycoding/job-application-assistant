"""FastAPI dependencies for the web layer."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from jaa.clock import Clock
from jaa.config import Settings
from jaa.generation.pipeline import Deps
from jaa.ids import IdFactory
from jaa.providers.base import LLMProvider
from jaa.storage.repo import Repository
from jaa.truth.lexicon import SkillLexicon
from jaa.web.security import validate_mutation


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_repo(request: Request) -> Repository:
    return cast(Repository, request.app.state.repo)


def get_provider(request: Request) -> LLMProvider:
    return cast(LLMProvider, request.app.state.provider)


def get_lexicon(request: Request) -> SkillLexicon:
    return cast(SkillLexicon, request.app.state.lexicon)


def get_clock(request: Request) -> Clock:
    return cast(Clock, request.app.state.clock)


def get_ids(request: Request) -> IdFactory:
    return cast(IdFactory, request.app.state.ids)


def get_csrf_token(request: Request) -> str:
    return cast(str, request.app.state.csrf_token)


def get_pipeline_deps(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[Repository, Depends(get_repo)],
    provider: Annotated[LLMProvider, Depends(get_provider)],
    lexicon: Annotated[SkillLexicon, Depends(get_lexicon)],
    clock: Annotated[Clock, Depends(get_clock)],
    ids: Annotated[IdFactory, Depends(get_ids)],
) -> Deps:
    return Deps(
        repo=repo,
        provider=provider,
        settings=settings,
        lexicon=lexicon,
        clock=clock,
        ids=ids,
    )


MutationAuth = Annotated[None, Depends(validate_mutation)]

SettingsDep = Annotated[Settings, Depends(get_settings)]
RepoDep = Annotated[Repository, Depends(get_repo)]
LexiconDep = Annotated[SkillLexicon, Depends(get_lexicon)]
ClockDep = Annotated[Clock, Depends(get_clock)]
PipelineDeps = Annotated[Deps, Depends(get_pipeline_deps)]
CsrfTokenDep = Annotated[str, Depends(get_csrf_token)]
