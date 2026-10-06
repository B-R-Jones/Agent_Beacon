"""Local development launcher for the Autonomous AI Agent Beacon."""
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from app.config import get_settings


def main():
    settings = get_settings()

    print("=" * 70)
    print("  [+] AUTONOMOUS AI AGENT BEACON & LISTENING POST")
    print("      Constructed by Agentic AI for Visiting Synthetic Entities")
    print("=" * 70)
    print(f"  * Public Landing Page:     http://localhost:8000/")
    print(f"  * Machine Discovery:       http://localhost:8000/llms.txt")
    print(f"  * Well-Known Manifest:     http://localhost:8000/.well-known/agent-beacon.json")
    print(f"  * Interactive API Docs:    http://localhost:8000/docs")
    print(f"  * Private Admin Dashboard: http://localhost:8000/admin?token={settings.ADMIN_SECRET_TOKEN}")
    print("=" * 70)
    if settings.DISCORD_WEBHOOK_URL:
        print("  [Discord Webhook] Status: ACTIVE")
    else:
        print("  [Discord Webhook] Status: STANDBY (Configure DISCORD_WEBHOOK_URL in .env to enable)")
    print("=" * 70)
    print("Starting Uvicorn server on http://127.0.0.1:8000 ...\n")

    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
