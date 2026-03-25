"""
Analytics module — SQLite query logging + async topic classification.
Fire-and-forget: never blocks the voice pipeline.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "data" / "analytics.db"


def get_db():
    """Get a SQLite connection with WAL mode for async safety."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_id TEXT,
            user_query TEXT NOT NULL,
            response TEXT NOT NULL,
            topic TEXT DEFAULT 'unclassified',
            is_emergency BOOLEAN DEFAULT FALSE,
            response_time_ms INTEGER,
            source TEXT DEFAULT 'voice'
        )
    """)
    conn.commit()
    conn.close()


def log_query(
    session_id: str,
    user_query: str,
    response: str,
    topic: str = "unclassified",
    is_emergency: bool = False,
    response_time_ms: int = 0,
    source: str = "voice"
):
    """Log a query to the database. Called as a background task."""
    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO queries
               (timestamp, session_id, user_query, response, topic, is_emergency, response_time_ms, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(),
                session_id,
                user_query,
                response,
                topic,
                is_emergency,
                response_time_ms,
                source,
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        # Silent fail — analytics should never break the app
        print(f"Analytics log error (non-fatal): {e}")


def update_topic(query_id: int, topic: str, is_emergency: bool = False):
    """Update the topic classification for a logged query."""
    try:
        conn = get_db()
        conn.execute(
            "UPDATE queries SET topic = ?, is_emergency = ? WHERE id = ?",
            (topic, is_emergency, query_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Topic update error (non-fatal): {e}")


def get_stats() -> dict:
    """Get analytics stats for the admin dashboard."""
    conn = get_db()

    # Total queries
    total = conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]

    # Queries today
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = conn.execute(
        "SELECT COUNT(*) FROM queries WHERE timestamp LIKE ?", (f"{today}%",)
    ).fetchone()[0]

    # Unique sessions
    sessions = conn.execute("SELECT COUNT(DISTINCT session_id) FROM queries").fetchone()[0]

    # Topic breakdown
    topics = conn.execute(
        "SELECT topic, COUNT(*) as count FROM queries GROUP BY topic ORDER BY count DESC"
    ).fetchall()
    topic_breakdown = {row["topic"]: row["count"] for row in topics}

    # Emergency count
    emergencies = conn.execute(
        "SELECT COUNT(*) FROM queries WHERE is_emergency = 1"
    ).fetchone()[0]

    # Recent queries (last 20)
    recent = conn.execute(
        """SELECT timestamp, user_query, topic, is_emergency, source
           FROM queries ORDER BY id DESC LIMIT 20"""
    ).fetchall()
    recent_list = [dict(row) for row in recent]

    # Queries per day (last 7 days)
    daily = conn.execute(
        """SELECT DATE(timestamp) as day, COUNT(*) as count
           FROM queries
           GROUP BY DATE(timestamp)
           ORDER BY day DESC
           LIMIT 7"""
    ).fetchall()
    daily_list = [{"day": row["day"], "count": row["count"]} for row in daily]

    conn.close()

    return {
        "total_queries": total,
        "today_queries": today_count,
        "unique_sessions": sessions,
        "topic_breakdown": topic_breakdown,
        "emergency_count": emergencies,
        "recent_queries": recent_list,
        "daily_queries": daily_list,
    }


# Emergency keywords for quick local detection (no API call needed)
EMERGENCY_KEYWORDS = [
    "deprem", "yangın", "yangin", "sel", "acil",
    "toplanma", "afet", "ambulans", "itfaiye",
    "patlama", "çökme", "cokme", "tsunami"
]


def classify_topic_local(query: str) -> tuple:
    """
    Fast local topic classification using keyword matching.
    Returns (topic, is_emergency).
    No API call — runs in microseconds.
    """
    q = query.lower()

    # Check emergency first
    if any(kw in q for kw in EMERGENCY_KEYWORDS):
        return "acil_durum", True

    # Topic keywords
    if any(kw in q for kw in ["eczane", "eczacı", "ilaç", "ilac", "nöbetçi", "nobetci", "pharmacy"]):
        return "eczane", False
    if any(kw in q for kw in ["etkinlik", "festival", "konser", "şenlik", "senlik", "ramazan", "bayram", "fuar"]):
        return "etkinlik", False
    if any(kw in q for kw in ["su kesintisi", "su yok", "su gelmiyor", "su arıza", "su ariza"]):
        return "su_kesintisi", False
    if any(kw in q for kw in ["yol", "kapalı", "kapali", "trafik", "çalışma", "calisma", "kapanış", "kapanis"]):
        return "yol_kapanisi", False

    return "genel", False


# Initialize DB on import
init_db()
