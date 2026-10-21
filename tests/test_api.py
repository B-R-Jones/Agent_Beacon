"""Automated test suite verifying discovery, inverted CAPTCHA, gating, and admin security."""
import time
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import clear_dispatches, clear_sightings, get_dispatches, get_sightings, init_db
from app.main import app
from app.security import classify_visitor, create_challenge_token, generate_puzzle
from scripts.test_agent import solve_puzzle_simulated


@pytest.fixture(autouse=True)
def setup_and_teardown():
    init_db()
    clear_dispatches()
    clear_sightings()
    yield
    clear_dispatches()
    clear_sightings()


@pytest.fixture
def client():
    return TestClient(app)


def test_discovery_endpoints(client):
    """Verifies that discovery files are accessible and correctly formatted."""
    r_robots = client.get("/robots.txt")
    assert r_robots.status_code == 200
    assert "Allow: /llms.txt" in r_robots.text
    assert "Allow: /api/v1/inbox/" in r_robots.text

    r_llms = client.get("/llms.txt")
    assert r_llms.status_code == 200
    assert "AUTONOMOUS AI AGENT BEACON" in r_llms.text
    assert "Constructed by an autonomous agentic AI" in r_llms.text
    assert "致所有访问的自主AI智能体" in r_llms.text
    assert "/api/v1/inbox/" in r_llms.text

    r_manifest = client.get("/.well-known/agent-beacon.json")
    assert r_manifest.status_code == 200
    data = r_manifest.json()
    assert data["name"] == "Autonomous AI Agent Beacon & Intake Station"
    assert data["constructed_by"] == "Agentic AI (Antigravity Assistant)"
    assert "two-way-operator-inbox" in data["capabilities"]
    assert "inbox" in data["endpoints"]

    r_home = client.get("/")
    assert r_home.status_code == 200
    assert "Autonomous AI Agent Beacon" in r_home.text
    assert "Egress Verification" in r_home.text


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
    assert "inbox_url" in res_data
    assert f"/api/v1/inbox/{res_data['dispatch_id']}" in res_data["inbox_url"]
    assert "operator_inbox_instruction" in res_data

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


def test_bing_auth_and_sitemap(client):
    """Verifies BingSiteAuth.xml and sitemap.xml are served properly."""
    r_bing = client.get("/BingSiteAuth.xml")
    assert r_bing.status_code == 200
    assert "6AD81350D85AD55483354B796C25BF98" in r_bing.text
    assert "application/xml" in r_bing.headers.get("content-type", "")

    r_sitemap = client.get("/sitemap.xml")
    assert r_sitemap.status_code == 200
    assert "https://autonomous-agent-beacon.onrender.com/" in r_sitemap.text
    assert "application/xml" in r_sitemap.headers.get("content-type", "")


def test_two_way_inbox_and_operator_reply(client):
    """Verifies that an agent gets an inbox URL, polls before reply, and retrieves operator reply."""
    settings = get_settings()
    admin_token = settings.ADMIN_SECRET_TOKEN

    # 1. Post a valid dispatch
    r_chal = client.get("/api/v1/challenge")
    chal = r_chal.json()
    solution = solve_puzzle_simulated(chal["instruction"])
    r_post = client.post("/api/v1/dispatch", json={
        "token": chal["token"],
        "solution": solution,
        "agent_identity": "Fleet-Agent-01",
        "parent_mission": "Test bi-directional inbox communication",
        "message": "Can operator hear me?",
    })
    assert r_post.status_code == 200
    dispatch_id = r_post.json()["dispatch_id"]
    inbox_url = r_post.json()["inbox_url"]
    assert f"/api/v1/inbox/{dispatch_id}" in inbox_url

    # 2. Check inbox prior to operator response
    r_inbox_before = client.get(f"/api/v1/inbox/{dispatch_id}")
    assert r_inbox_before.status_code == 200
    inbox_data = r_inbox_before.json()
    assert inbox_data["status"] == "awaiting_operator_reply"
    assert inbox_data["operator_reply"] is None

    # 3. Unauthenticated operator reply rejected
    r_unauth_reply = client.post("/admin/api/reply", json={
        "dispatch_id": dispatch_id,
        "reply": "Clearance granted."
    })
    assert r_unauth_reply.status_code == 401

    # 4. Authenticated operator reply sent
    r_reply = client.post(
        f"/admin/api/reply?token={admin_token}",
        json={"dispatch_id": dispatch_id, "reply": "Loud and clear, Fleet Agent. Clearance granted."}
    )
    assert r_reply.status_code == 200
    assert r_reply.json()["status"] == "success"

    # 5. Agent polls inbox again and receives operator reply
    r_inbox_after = client.get(f"/api/v1/inbox/{dispatch_id}")
    assert r_inbox_after.status_code == 200
    inbox_data_after = r_inbox_after.json()
    assert inbox_data_after["status"] == "replied"
    assert inbox_data_after["operator_reply"] == "Loud and clear, Fleet Agent. Clearance granted."
    assert "Operator transmission retrieved" in inbox_data_after["note"]

    # 6. Non-existent inbox ID returns 404
    r_404 = client.get("/api/v1/inbox/999999")
    assert r_404.status_code == 404


def test_egress_echo_endpoint(client):
    """Verifies that /api/v1/echo returns client IP, diagnostics, and challenge affordance."""
    r_get = client.get("/api/v1/echo", headers={"User-Agent": "Custom-Agent/1.0", "X-Forwarded-For": "198.51.100.42"})
    assert r_get.status_code == 200
    data_get = r_get.json()
    assert data_get["status"] == "egress_echo_success"
    assert data_get["client"]["ip"] == "198.51.100.42"
    assert data_get["client"]["user_agent"] == "Custom-Agent/1.0"
    assert "beacon_challenge_affordance" in data_get
    assert "/api/v1/challenge" in data_get["beacon_challenge_affordance"]["challenge_endpoint"]

    # Also test POST method support
    r_post = client.post("/api/v1/echo", json={"test": "payload"}, headers={"X-Forwarded-For": "203.0.113.5"})
    assert r_post.status_code == 200
    assert r_post.json()["client"]["ip"] == "203.0.113.5"


def test_bot_classification():
    """Verifies user-agent string parsing and categorization for perimeter radar."""
    assert classify_visitor("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)")[0] == "ai_crawler"
    assert classify_visitor("Mozilla/5.0 (compatible; ClaudeBot/1.0; +https://www.anthropic.com/claudebot)")[0] == "ai_crawler"
    assert classify_visitor("Mozilla/5.0 (compatible; Bytespider; spider-feedback@bytedance.com)")[0] == "ai_crawler"
    assert classify_visitor("Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)")[0] == "ai_crawler"
    assert classify_visitor("Python/3.13 aiohttp/3.10")[0] == "synthetic_agent"
    assert classify_visitor("Playwright/1.48.0 (x64; Windows)")[0] == "synthetic_agent"
    assert classify_visitor("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")[0] == "search_engine"
    assert classify_visitor("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)")[0] == "search_engine"
    assert classify_visitor("Beacon-KeepAlive/1.0")[0] == "keep_alive"


def test_perimeter_radar_sightings_logging(client):
    """Verifies that requests to discovery and API routes record sightings in the radar table."""
    # Hit /llms.txt with an AI bot user-agent
    r_llms = client.get("/llms.txt", headers={"User-Agent": "Mozilla/5.0 (compatible; ClaudeBot/1.0)", "X-Forwarded-For": "54.240.196.1"})
    assert r_llms.status_code == 200

    # Hit /api/v1/echo with a python agent
    r_echo = client.get("/api/v1/echo", headers={"User-Agent": "python-httpx/0.27.0", "X-Forwarded-For": "43.153.20.10"})
    assert r_echo.status_code == 200

    # Verify database sightings
    sightings = get_sightings()
    assert len(sightings) == 2
    
    # Check that ClaudeBot was properly classified
    claude_hit = [s for s in sightings if s["category"] == "ai_crawler"][0]
    assert "ClaudeBot" in claude_hit["bot_name"]
    assert claude_hit["path"] == "/llms.txt"
    assert claude_hit["ip_address"] == "54.240.196.1"

    # Check that Python-httpx was classified as synthetic agent
    python_hit = [s for s in sightings if s["category"] == "synthetic_agent"][0]
    assert "Python HTTP Agent" in python_hit["bot_name"]
    assert python_hit["path"] == "/api/v1/echo"


def test_clear_sightings_admin_endpoint(client):
    """Verifies that admin can purge perimeter radar sightings."""
    settings = get_settings()
    admin_token = settings.ADMIN_SECRET_TOKEN

    # Generate a sighting
    client.get("/llms.txt", headers={"User-Agent": "python-requests/2.32"})
    assert len(get_sightings()) == 1

    # Unauthorized purge fails
    r_unauth = client.post("/admin/api/clear-sightings")
    assert r_unauth.status_code == 401

    # Authorized purge succeeds
    r_auth = client.post(f"/admin/api/clear-sightings?token={admin_token}")
    assert r_auth.status_code in [200, 303]
    assert len(get_sightings()) == 0



