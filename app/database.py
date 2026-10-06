"""Database layer: SQLite storage with auto-pruning and analytics."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import get_settings


def get_db_path() -> str:
    settings = get_settings()
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        path_str = url.replace("sqlite:///", "")
        return path_str
    return "./beacon.db"


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database schema and indexes."""
    db_path = get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dispatches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                agent_identity TEXT NOT NULL,
                parent_mission TEXT,
                message TEXT NOT NULL,
                software_stack TEXT,
                solve_latency_ms INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                extra_headers TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dispatches_created_at ON dispatches(created_at DESC)")
        conn.commit()


def insert_dispatch(
    agent_identity: str,
    parent_mission: Optional[str],
    message: str,
    software_stack: Optional[str],
    solve_latency_ms: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra_headers: Optional[Dict[str, Any]] = None,
) -> int:
    """Inserts a verified agent dispatch and auto-prunes old records beyond MAX_STORED_DISPATCHES."""
    settings = get_settings()
    now_iso = datetime.now(timezone.utc).isoformat()
    headers_json = json.dumps(extra_headers or {})

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO dispatches (
                created_at, agent_identity, parent_mission, message,
                software_stack, solve_latency_ms, ip_address, user_agent, extra_headers
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso,
                agent_identity[:150],
                (parent_mission or "")[:500],
                message[:1500],
                (software_stack or "")[:200],
                solve_latency_ms,
                (ip_address or "")[:64],
                (user_agent or "")[:300],
                headers_json,
            ),
        )
        dispatch_id = cursor.lastrowid

        # FIFO auto-pruning to guarantee bounded storage
        cursor.execute("SELECT COUNT(*) FROM dispatches")
        total_count = cursor.fetchone()[0]
        if total_count > settings.MAX_STORED_DISPATCHES:
            excess = total_count - settings.MAX_STORED_DISPATCHES
            cursor.execute(
                "DELETE FROM dispatches WHERE id IN (SELECT id FROM dispatches ORDER BY id ASC LIMIT ?)",
                (excess,),
            )

        conn.commit()
        return dispatch_id


def get_dispatches(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves paginated dispatches ordered by newest first."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, created_at, agent_identity, parent_mission, message,
                   software_stack, solve_latency_ms, ip_address, user_agent, extra_headers
            FROM dispatches
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["extra_headers"] = json.loads(d["extra_headers"]) if d["extra_headers"] else {}
            except Exception:
                d["extra_headers"] = {}
            result.append(d)
        return result


def get_dispatch_stats() -> Dict[str, Any]:
    """Computes aggregate analytics for the admin dashboard."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dispatches")
        total_count = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(solve_latency_ms) FROM dispatches")
        avg_latency_raw = cursor.fetchone()[0]
        avg_latency_ms = int(avg_latency_raw) if avg_latency_raw is not None else 0

        cursor.execute(
            """
            SELECT agent_identity, COUNT(*) as cnt
            FROM dispatches
            GROUP BY agent_identity
            ORDER BY cnt DESC
            LIMIT 5
            """
        )
        top_identities = [{"identity": row[0], "count": row[1]} for row in cursor.fetchall()]

        return {
            "total_dispatches": total_count,
            "average_latency_ms": avg_latency_ms,
            "top_identities": top_identities,
        }


def clear_dispatches() -> int:
    """Purges all dispatches from the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dispatches")
        deleted = cursor.rowcount
        conn.commit()
        return deleted
