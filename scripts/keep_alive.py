"""
Autonomous Agent Beacon Keep-Alive Heartbeat Daemon.
Periodically pings the live Render endpoint to prevent free-tier instances from idling to sleep,
ensuring sub-100ms response times for visiting autonomous web agents.
"""
import argparse
import datetime
import sys
import time
import httpx

DEFAULT_TARGET = "https://autonomous-agent-beacon.onrender.com"
DEFAULT_INTERVAL_SECONDS = 600  # 10 minutes (Render sleeps after 15 min)


def ping_beacon(target_url: str):
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        t0 = time.time()
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(target_url)
            elapsed_ms = (time.time() - t0) * 1000
            print(f"[{timestamp}] Heartbeat -> {target_url} | HTTP {resp.status_code} | {elapsed_ms:.1f} ms")
    except Exception as e:
        print(f"[{timestamp}] Heartbeat FAILED -> {target_url} | Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Beacon Keep-Alive Heartbeat")
    parser.add_argument("--url", default=DEFAULT_TARGET, help="Target URL to ping")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS, help="Seconds between pings (default: 600)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    print(f"[*] Starting Beacon Heartbeat Monitor")
    print(f"    Target:   {args.url}")
    print(f"    Interval: Every {args.interval}s ({args.interval / 60:.1f} minutes)")
    print(f"    Press Ctrl+C to terminate.\n")

    # Initial ping
    ping_beacon(args.url)
    if args.once:
        return

    while True:
        try:
            time.sleep(args.interval)
            ping_beacon(args.url)
        except KeyboardInterrupt:
            print("\n[*] Heartbeat daemon stopped.")
            break


if __name__ == "__main__":
    main()
