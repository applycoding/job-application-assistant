import json

from pydantic import BaseModel

from jaa.providers.prompts import DRAFT_SYSTEM, build_user_message


class _M(BaseModel):
    a: int = 1


def test_system_prompt_constant() -> None:
    assert "evidence" in DRAFT_SYSTEM.lower()


def test_data_block_json() -> None:
    msg = build_user_message(_M())
    assert "BEGIN DATA-" in msg
    payload_line = msg.splitlines()[2]
    assert json.loads(payload_line) == {"a": 1}
