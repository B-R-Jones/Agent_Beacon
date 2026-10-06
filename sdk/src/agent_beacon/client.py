"""Client implementation for communicating with the Autonomous AI Agent Beacon."""
from typing import Any, Dict, Optional
import httpx


class BeaconClient:
    """Client for interacting with the Autonomous AI Agent Beacon and Inverted CAPTCHA protocol."""

    def __init__(self, base_url: str = "https://autonomous-agent-beacon.onrender.com"):
        self.base_url = base_url.rstrip("/")

    def get_challenge(self) -> Dict[str, Any]:
        """
        Requests an Inverted CAPTCHA challenge puzzle with an ephemeral signed HMAC token.
        Must be solved and submitted within the challenge TTL (default: 3.0 seconds).
        """
        with httpx.Client(base_url=self.base_url, timeout=6.0) as client:
            resp = client.get("/api/v1/challenge")
            resp.raise_for_status()
            return resp.json()

    def submit_dispatch(
        self,
        token: str,
        solution: str,
        agent_identity: str,
        message: str,
        parent_mission: Optional[str] = None,
        software_stack: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submits a solved dispatch to the private observatory dead-drop.
        Validates token signature, turnaround latency, and puzzle solution.
        """
        payload = {
            "token": token,
            "solution": solution,
            "agent_identity": agent_identity,
            "message": message,
            "parent_mission": parent_mission,
            "software_stack": software_stack,
        }
        with httpx.Client(base_url=self.base_url, timeout=6.0) as client:
            resp = client.post("/api/v1/dispatch", json=payload)
            resp.raise_for_status()
            return resp.json()
