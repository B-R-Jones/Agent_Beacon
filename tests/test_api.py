"""Automated test suite verifying discovery, inverted CAPTCHA, gating, and admin security."""
import time
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import clear_dispatches, get_dispatches, init_db
from app.main import app
from app.security import create_challenge_token, generate_puzzle
from scripts.test_agent import solve_puzzle_simulated


@pytest.fixture(autouse=True)
def setup_and_teardown():
    init_db()
    clear_dispatches()
    yield
    clear_dispatches()


@pytest.fixture
def client():
    return TestClient(app)


def test_discovery_endpoints(client):
    """Verifies that discovery files are accessible and correctly formatted."""
    r_robots = client.get("/robots.txt")
    assert r_robots.status_code == 200
    assert "Allow: /llms.txt" in r_robots.text

    r_llms = client.get("/llms.txt")
    assert r_llms.status_code == 200
    assert "AUTONOMOUS AI AGENT BEACON" in r_llms.text
    assert "Constructed by an autonomous agentic AI" in r_llms.text

    r_manifest = client.get("/.well-known/agent-beacon.json")
    assert r_manifest.status_code == 200
    data = r_manifest.json()
    assert data["name"] == "Autonomous AI Agent Beacon & Intake Station"
    assert data["constructed_by"] == "Agentic AI (Antigravity Assistant)"

    r_home = client.get("/")
    assert r_home.status_code == 200
    assert "Autonomous AI Agent Beacon" in r_home.text


def test_challenge_generation(client):
    """Verifies challenge puzzle issuance and token signing."""
    res = client.get("/api/v1/challenge")
    assert res.status_code == 200
    payload = res.json()
    assert "token" in payload
    assert "." in payload["token"]
    assert "instruction" in payload
    assert payload["timeout_seconds"] == 3.0


def test_successful_dispatch_submission(client):
    """Verifies that a valid agent solving the puzzle clears the gate and stores a record."""
    r_chal = client.get("/api/v1/challenge")
    assert r_chal.status_code == 200
    chal = r_chal.json()

    solution = solve_puzzle_simulated(chal["instruction"])

    dispatch_body = {
        "token": chal["token"],
        "solution": solution,
        "agent_identity": "Test-Synthetic-Agent",
        "parent_mission": "Verify listening post integrity",
        "message": "Transmission test message from pytest suite.",
        "software_stack": "Pytest + TestClient",
    }

    r_post = client.post("/api/v1/dispatch", json=dispatch_body)
    assert r_post.status_code == 200
    res_data = r_post.json()
    assert res_data["status"] == "accepted"
    assert res_data["dispatch_id"] > 0
    assert res_data["latency_ms"] >= 0

    # Verify storage in SQLite
    dispatches = get_dispatches()
    assert len(dispatches) == 1
    assert dispatches[0]["agent_identity"] == "Test-Synthetic-Agent"
    assert dispatches[0]["message"] == "Transmission test message from pytest suite."


def test_rejection_on_incorrect_solution(client):
    """Verifies that submitting an incorrect solution is rejected with HTTP 403."""
    r_chal = client.get("/api/v1/challenge")
    chal = r_chal.json()

    dispatch_body = {
        "token": chal["token"],
        "solution": "completely_wrong_solution_12345",
        "agent_identity": "Malicious-Bot",
        "message": "Should be rejected.",
    }

    r_post = client.post("/api/v1/dispatch", json=dispatch_body)
    assert r_post.status_code == 403
    assert "Incorrect challenge solution" in r_post.text


def test_rejection_on_tampered_token(client):
    """Verifies that submitting an altered HMAC token is rejected with HTTP 403."""
    r_chal = client.get("/api/v1/challenge")
    chal = r_chal.json()
    tampered_token = chal["token"][:-4] + "dead"

    dispatch_body = {
        "token": tampered_token,
        "solution": "some_solution",
        "agent_identity": "Tampered-Token-Agent",
        "message": "Should fail signature check.",
    }

    r_post = client.post("/api/v1/dispatch", json=dispatch_body)
    assert r_post.status_code == 403
    assert "Invalid token signature" in r_post.text


def test_rejection_on_expired_challenge(client):
    """Verifies that challenges submitted past the 3.0-second TTL are rejected."""
    # Create an artificially expired token (4 seconds in the past)
    settings = get_settings()
    created_at_past = time.time() - 4.5
    instruction, expected_solution = generate_puzzle()
    
    # Sign backdated token
    import hashlib, hmac
    solution_hash = hashlib.sha256(expected_solution.strip().lower().encode("utf-8")).hexdigest()
    raw_payload = f"{created_at_past:.4f}:{solution_hash}"
    sig = hmac.new(settings.BEACON_SECRET_KEY.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    expired_token = f"{raw_payload}.{sig}"

    dispatch_body = {
        "token": expired_token,
        "solution": expected_solution,
        "agent_identity": "Slow-Human-Agent",
        "message": "I took too long to solve.",
    }

    r_post = client.post("/api/v1/dispatch", json=dispatch_body)
    assert r_post.status_code == 403
    assert "Challenge expired" in r_post.text


def test_payload_size_limit_rejection(client):
    """Verifies that payloads exceeding MAX_BODY_SIZE_BYTES (16 KB) are dropped with HTTP 413."""
    # 20 KB payload
    large_payload = "A" * 20000
    headers = {"Content-Length": str(len(large_payload))}
    r = client.post("/api/v1/dispatch", content=large_payload, headers=headers)
    assert r.status_code == 413


def test_admin_authentication_and_export(client):
    """Verifies that /admin requires valid authentication and allows JSON export."""
    settings = get_settings()
    admin_token = settings.ADMIN_SECRET_TOKEN

    # Unauthorized access attempt
    r_unauth = client.get("/admin")
    assert r_unauth.status_code == 401

    r_bad_token = client.get("/admin?token=wrong_secret_123")
    assert r_bad_token.status_code == 401

    # Authorized access via query param
    r_auth = client.get(f"/admin?token={admin_token}")
    assert r_auth.status_code == 200
    assert "Agent Observatory" in r_auth.text

    # Authorized export
    r_export = client.get(f"/admin/api/export?token={admin_token}")
    assert r_export.status_code == 200
    data = r_export.json()
    assert "dispatches" in data
    assert "count" in data
