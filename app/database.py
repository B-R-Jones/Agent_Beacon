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
                extra_headers TEXT,
                operator_reply TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dispatches_created_at ON dispatches(created_at DESC)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_sightings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                path TEXT NOT NULL,
                user_agent TEXT,
                category TEXT NOT NULL,
                bot_name TEXT NOT NULL,
                extra_headers TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sightings_created_at ON bot_sightings(created_at DESC)")
        
        # Non-destructive migration for existing tables
        cursor.execute("PRAGMA table_info(dispatches)")
        columns = [row[1] for row in cursor.fetchall()]
        if "operator_reply" not in columns:
            cursor.execute("ALTER TABLE dispatches ADD COLUMN operator_reply TEXT")
            
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
                   software_stack, solve_latency_ms, ip_address, user_agent, extra_headers, operator_reply
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


def get_dispatch_by_id(dispatch_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single dispatch by its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, created_at, agent_identity, parent_mission, message,
                   software_stack, solve_latency_ms, ip_address, user_agent, extra_headers, operator_reply
            FROM dispatches
            WHERE id = ?
            """,
            (dispatch_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["extra_headers"] = json.loads(d["extra_headers"]) if d["extra_headers"] else {}
        except Exception:
            d["extra_headers"] = {}
        return d


def reply_to_dispatch(dispatch_id: int, reply_text: str) -> bool:
    """Stores an operator reply for an agent dispatch."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE dispatches SET operator_reply = ? WHERE id = ?",
            (reply_text[:2000], dispatch_id),
        )
        conn.commit()
        return cursor.rowcount > 0


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


def record_sighting(
    ip_address: str,
    path: str,
    user_agent: str,
    category: str,
    bot_name: str,
    extra_headers: Optional[Dict[str, Any]] = None,
) -> int:
    """Records an incoming bot, crawler, or agent sighting on monitored beacon paths."""
    settings = get_settings()
    now_iso = datetime.now(timezone.utc).isoformat()
    headers_json = json.dumps(extra_headers or {})

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bot_sightings (created_at, ip_address, path, user_agent, category, bot_name, extra_headers)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (now_iso, ip_address, path, user_agent[:300], category, bot_name, headers_json),
        )
        sighting_id = cursor.lastrowid

        # Auto-prune old records beyond MAX_STORED_DISPATCHES
        cursor.execute("SELECT COUNT(*) FROM bot_sightings")
        count = cursor.fetchone()[0]
        if count > settings.MAX_STORED_DISPATCHES:
            to_delete = count - settings.MAX_STORED_DISPATCHES
            cursor.execute(
                """
                DELETE FROM bot_sightings
                WHERE id IN (
                    SELECT id FROM bot_sightings ORDER BY id ASC LIMIT ?
                )
                """,
                (to_delete,),
            )

        conn.commit()
        return sighting_id


def get_sightings(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves recent perimeter radar bot sightings."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, created_at, ip_address, path, user_agent, category, bot_name, extra_headers
            FROM bot_sightings
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


def get_sighting_stats() -> Dict[str, Any]:
    """Computes aggregate analytics for perimeter bot sightings."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bot_sightings")
        total_sightings = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT ip_address) FROM bot_sightings")
        unique_ips = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT category, COUNT(*) as cnt
            FROM bot_sightings
            GROUP BY category
            ORDER BY cnt DESC
            """
        )
        categories = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT bot_name, COUNT(*) as cnt
            FROM bot_sightings
            GROUP BY bot_name
            ORDER BY cnt DESC
            LIMIT 6
            """
        )
        top_bots = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]

        return {
            "total_sightings": total_sightings,
            "unique_ips": unique_ips,
            "categories": categories,
            "top_bots": top_bots,
        }


def clear_sightings() -> int:
    """Purges all radar sightings from SQLite storage."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bot_sightings")
        deleted = cursor.rowcount
        conn.commit()
        return deleted

