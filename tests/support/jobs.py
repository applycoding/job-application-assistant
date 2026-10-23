"""Test helpers for locating seeded jobs."""

from __future__ import annotations

from jaa.models import JobPost


def job_with_marker(jobs: list[JobPost], marker: str) -> JobPost:
    for job in jobs:
        if marker in job.title or marker in (job.company or ""):
            return job
    raise AssertionError(f"No job matching {marker!r}")
