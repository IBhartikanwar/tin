"""Offline unit tests for the growth.release_announce contributed workflow package.

Validates the manifest contract, two-step model sequence, grounding constraints,
and output rendering without making paid supplier API calls.
"""

from __future__ import annotations

import json
import runpy
from types import SimpleNamespace

import jsonschema
import pytest

from tin_lite.code_models import model_terms, request_contract
from tin_lite.community import REPOSITORY_ROOT
from tin_lite.workflow_code import validate_code_definition, validate_code_result

PACKAGE_KEY = "growth.release_announce"


def load_package():
    root = REPOSITORY_ROOT / "workflow_packages" / PACKAGE_KEY
    definition = json.loads((root / "workflow.json").read_text())["definition"]
    module = SimpleNamespace(**runpy.run_path(str(root / "main.py")))
    return module, definition


def test_package_contract_and_estimate():
    _, definition = load_package()
    spec = validate_code_definition(definition)
    assert spec.entrypoint == "main.py"
    assert spec.output_path == "reports/RELEASE_ANNOUNCE.md"
    assert spec.media_type == "text/markdown"
    assert spec.max_bytes == 32000
    assert len(spec.model_routes) == 2
    assert {r.name for r in spec.model_routes} == {"extract", "announce"}
    terms = model_terms(definition)
    assert terms["maximum_nanos"] > 0


@pytest.mark.parametrize("tone", ["professional", "enthusiastic"])
async def test_happy_path_two_model_steps_and_report_rendering(tone):
    module, definition = load_package()
    spec = validate_code_definition(definition)
    calls = []

    changelog_sample = (
        "# Release 2.4.0\n"
        "---\n"
        "- Added CSV export for customer analytics\n"
        "- Fixed bug causing session timeout on Safari\n"
        "- Refactored database connection pool internals\n"
    )

    async def generate(**payload):
        request_contract(spec, payload)
        calls.append(payload)
        if payload["step"] == "extract_changes":
            output = {
                "changes": [
                    {
                        "id": 1,
                        "summary": "CSV export for customer analytics",
                        "category": "feature",
                        "user_facing": True,
                    },
                    {
                        "id": 2,
                        "summary": "Resolved session timeout bug on Safari",
                        "category": "fix",
                        "user_facing": True,
                    },
                    {
                        "id": 3,
                        "summary": "Internal refactor of database pool",
                        "category": "internal",
                        "user_facing": False,
                    },
                ]
            }
        elif payload["step"] == "write_announcements":
            # Assert that ONLY user_facing changes were passed to the announce step
            assert len(payload["data"]) == 2
            assert all(item["user_facing"] for item in payload["data"])
            output = {
                "twitter": "We just shipped v2.4.0: CSV analytics export and Safari fixes!",
                "linkedin": "Excited to share our v2.4.0 release featuring CSV analytics export.",
                "email_subject": "What's new in v2.4.0: CSV Export & Safari Fixes",
                "email_body": (
                    "Hi there,\n\nWe've released CSV export for your analytics.\n\nBest,\nThe Team"
                ),
            }
        else:
            raise ValueError(f"Unexpected step: {payload['step']}")

        jsonschema.validate(output, payload["output_schema"])
        return {"parsed": output, "text": json.dumps(output)}

    ctx = SimpleNamespace(models=SimpleNamespace(generate=generate))
    inputs = {
        "project_id": "a0000000-0000-0000-0000-000000000001",
        "changelog": changelog_sample,
        "product_name": "Tin Computer",
        "audience": "Founders and growth engineers",
        "tone": tone,
    }

    result = await module.run(ctx, inputs)
    assert [c["step"] for c in calls] == ["extract_changes", "write_announcements"]
    assert result["path"] == "reports/RELEASE_ANNOUNCE.md"
    assert "# Release announcements for Tin Computer" in result["content"]
    assert "## Twitter / X" in result["content"]
    assert "## LinkedIn" in result["content"]
    assert "## Email" in result["content"]
    assert "1 internal change(s) omitted from announcements." in result["content"]
    assert f"Tone: {tone}" in result["content"]
    validate_code_result(json.dumps(result).encode(), spec)


@pytest.mark.parametrize(
    "bad_changes,error_match",
    [
        (
            [
                {
                    "id": 99,
                    "summary": "Hallucinated feature",
                    "category": "feature",
                    "user_facing": True,
                }
            ],
            "out of range",
        ),
        (
            [
                {
                    "id": 0,
                    "summary": "Duplicate entry 1",
                    "category": "feature",
                    "user_facing": True,
                },
                {
                    "id": 0,
                    "summary": "Duplicate entry 2",
                    "category": "feature",
                    "user_facing": True,
                },
            ],
            "duplicate",
        ),
        (
            [
                {
                    "id": 0,
                    "summary": "Internal refactor",
                    "category": "internal",
                    "user_facing": False,
                }
            ],
            "No user-facing changes found",
        ),
    ],
)
async def test_extraction_validation_rejects_hallucinated_or_internal_only(
    bad_changes, error_match
):
    module, definition = load_package()
    spec = validate_code_definition(definition)
    calls = []

    async def generate(**payload):
        request_contract(spec, payload)
        calls.append(payload)
        output = {"changes": bad_changes}
        jsonschema.validate(output, payload["output_schema"])
        return {"parsed": output, "text": json.dumps(output)}

    ctx = SimpleNamespace(models=SimpleNamespace(generate=generate))
    inputs = {
        "project_id": "a0000000-0000-0000-0000-000000000001",
        "changelog": "- Line zero change",
        "product_name": "Tin Computer",
    }

    with pytest.raises(ValueError, match=error_match):
        await module.run(ctx, inputs)
    assert len(calls) == 1  # Never proceeds to announce step on bad extraction


async def test_announcement_rejects_oversized_twitter_post():
    module, definition = load_package()
    spec = validate_code_definition(definition)

    async def generate(**payload):
        request_contract(spec, payload)
        if payload["step"] == "extract_changes":
            output = {
                "changes": [
                    {
                        "id": 0,
                        "summary": "New feature",
                        "category": "feature",
                        "user_facing": True,
                    }
                ]
            }
        else:
            output = {
                "twitter": "x" * 281,  # Exceeds Twitter 280-char limit
                "linkedin": "LinkedIn update",
                "email_subject": "Subject",
                "email_body": "Body",
            }
        return {"parsed": output, "text": json.dumps(output)}

    ctx = SimpleNamespace(models=SimpleNamespace(generate=generate))
    inputs = {
        "project_id": "a0000000-0000-0000-0000-000000000001",
        "changelog": "- New feature shipped",
        "product_name": "Tin Computer",
    }

    with pytest.raises(ValueError, match="Twitter post is 281 characters, max 280"):
        await module.run(ctx, inputs)


@pytest.mark.parametrize("empty_input", ["", "   ", "\n---\n===\n***", "--- \n === \n ~~~"])
async def test_split_changelog_rejects_empty_or_decorative_content(empty_input):
    module, _ = load_package()
    ctx = SimpleNamespace()
    inputs = {
        "project_id": "a0000000-0000-0000-0000-000000000001",
        "changelog": empty_input,
        "product_name": "Tin Computer",
    }
    with pytest.raises(ValueError, match="Changelog contains no meaningful content"):
        await module.run(ctx, inputs)
