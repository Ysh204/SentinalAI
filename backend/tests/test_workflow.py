from fastapi.testclient import TestClient

from backend.app.models.schemas import IncidentPublic
from backend.app.services.providers.mock_provider import SAMPLE_PATCH, MockProvider
from backend.app.services.validator import Validator
from backend.tests.conftest import BAD_PATCH, SAMPLE_PAYLOAD


def _create(client: TestClient) -> str:
    return client.post("/api/incidents", json=SAMPLE_PAYLOAD).json()["id"]


def test_mock_provider_analysis(client: TestClient) -> None:
    incident_id = _create(client)
    response = client.post(f"/api/incidents/{incident_id}/analyze")
    assert response.status_code == 200
    analysis = response.json()["root_cause_analysis"]
    assert analysis["provider"] == "mock"
    assert analysis["suspected_file"] == "buggy_app.py"
    assert analysis["suspected_function"] == "add"
    assert "not verified fact" in analysis["disclaimer"].lower()
    assert "subtract" in analysis["hypothesis"].lower() or "sum" in analysis["hypothesis"].lower()


def test_mock_patch_generation(client: TestClient) -> None:
    incident_id = _create(client)
    client.post(f"/api/incidents/{incident_id}/analyze")
    response = client.post(f"/api/incidents/{incident_id}/generate-patch")
    assert response.status_code == 200
    patch = response.json()["proposed_patch"]
    assert "--- a/buggy_app.py" in patch
    assert "return left + right" in patch
    assert response.json()["status"] == "PATCH_GENERATED"


def test_successful_patch_validation_and_approve(client: TestClient) -> None:
    incident_id = _create(client)
    client.post(f"/api/incidents/{incident_id}/analyze")
    client.post(f"/api/incidents/{incident_id}/generate-patch")
    validated = client.post(f"/api/incidents/{incident_id}/validate")
    assert validated.status_code == 200
    body = validated.json()
    assert body["status"] == "VALIDATED"
    assert body["validation_results"]["overall_passed"] is True
    pytest_check = next(
        check for check in body["validation_results"]["checks"] if check["name"] == "pytest"
    )
    assert pytest_check["status"] == "passed"

    approved = client.post(f"/api/incidents/{incident_id}/approve", json={"actor": "tester"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["approval"]["decision"] == "approved"


def test_failed_validation_via_validator_service(tmp_settings, container) -> None:
    incident = IncidentPublic(
        id="00000000-0000-0000-0000-000000000001",
        title="bad patch",
        error_message="boom",
        stack_trace="",
        repository_path="sample_app",
        status="PATCH_GENERATED",
        proposed_patch=BAD_PATCH,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    results = Validator(tmp_settings).validate(incident)
    assert results.overall_passed is False
    pytest_check = next(check for check in results.checks if check.name == "pytest")
    assert pytest_check.status == "failed"


def test_invalid_workflow_transitions(client: TestClient) -> None:
    incident_id = _create(client)
    too_early_patch = client.post(f"/api/incidents/{incident_id}/generate-patch")
    assert too_early_patch.status_code == 409

    too_early_validate = client.post(f"/api/incidents/{incident_id}/validate")
    assert too_early_validate.status_code == 409

    client.post(f"/api/incidents/{incident_id}/analyze")
    client.post(
        f"/api/incidents/{incident_id}/reject",
        json={"reason": "Stopping here."},
    )
    after_reject = client.post(f"/api/incidents/{incident_id}/analyze")
    assert after_reject.status_code == 409


def test_mock_provider_direct_patch_matches_sample() -> None:
    provider = MockProvider()
    from datetime import datetime, timezone

    from backend.app.models.schemas import AnalysisResult, IncidentPublic

    incident = IncidentPublic(
        id="x",
        title="sample",
        error_message="add(2, 3)",
        stack_trace="buggy_app",
        repository_path="sample_app",
        status="ANALYZED",
        root_cause_analysis=AnalysisResult(
            hypothesis="subtraction",
            suspected_file="buggy_app.py",
            suspected_function="add",
            provider="mock",
        ),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    draft = provider.generate_patch(incident, "return left - right  # BUG: should add")
    assert "return left + right" in draft.unified_diff
    assert SAMPLE_PATCH.strip() in draft.unified_diff
