from jaa.models import LLMDraftOut
from jaa.providers.schema import portable_json_schema


def test_schema_additional_properties_false():
    sch = portable_json_schema(LLMDraftOut)
    assert sch.get("additionalProperties") is False
