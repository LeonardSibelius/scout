"""
Scout Database — SQLite storage for opportunities and scan history.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'scout.db')


def get_db():
    """Get a database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            source TEXT NOT NULL,
            url TEXT,
            score REAL DEFAULT 0,
            domain TEXT,
            tags TEXT,
            raw_data TEXT,
            found_date TEXT NOT NULL,
            status TEXT DEFAULT 'new'
        );

        CREATE TABLE IF NOT EXISTS dismissed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL,
            dismissed_date TEXT NOT NULL,
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
        );

        CREATE TABLE IF NOT EXISTS bookmarked (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL,
            bookmarked_date TEXT NOT NULL,
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
        );

        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_date TEXT NOT NULL,
            opportunity_count INTEGER,
            subject TEXT
        );

        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_date TEXT NOT NULL,
            sources_scanned TEXT,
            items_found INTEGER DEFAULT 0,
            opportunities_added INTEGER DEFAULT 0,
            duration_seconds REAL DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


def save_opportunities(opportunities: List[Dict[str, Any]]) -> int:
    """Save scored opportunities to database. Returns count of new items added."""
    conn = get_db()
    added = 0
    for opp in opportunities:
        # Check for duplicate by URL or title
        existing = conn.execute(
            "SELECT id FROM opportunities WHERE url = ? OR title = ?",
            (opp.get('url', ''), opp.get('title', ''))
        ).fetchone()

        if not existing:
            conn.execute("""
                INSERT INTO opportunities (title, description, source, url, score, domain, tags, raw_data, found_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
            """, (
                opp.get('title', 'Untitled'),
                opp.get('description', ''),
                opp.get('source', 'unknown'),
                opp.get('url', ''),
                opp.get('score', 0),
                opp.get('domain', ''),
                opp.get('tags', ''),
                opp.get('raw_data', ''),
                datetime.now().isoformat()
            ))
            added += 1

    conn.commit()
    conn.close()
    return added


def get_opportunities(status: str = None, limit: int = 50, min_score: float = 0) -> List[Dict]:
    """Fetch opportunities, optionally filtered."""
    conn = get_db()
    query = "SELECT * FROM opportunities WHERE score >= ?"
    params = [min_score]

    if status:
        query += " AND status = ?"
        params.append(status)

    # Exclude dismissed
    query += " AND id NOT IN (SELECT opportunity_id FROM dismissed)"
    query += " ORDER BY score DESC, found_date DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_top_opportunities(limit: int = 5) -> List[Dict]:
    """Get top-scored non-dismissed opportunities for email digest."""
    return get_opportunities(status='new', limit=limit, min_score=5.0)


def dismiss_opportunity(opp_id: int):
    """Mark an opportunity as dismissed."""
    conn = get_db()
    conn.execute(
        "INSERT INTO dismissed (opportunity_id, dismissed_date) VALUES (?, ?)",
        (opp_id, datetime.now().isoformat())
    )
    conn.execute("UPDATE opportunities SET status = 'dismissed' WHERE id = ?", (opp_id,))
    conn.commit()
    conn.close()


def bookmark_opportunity(opp_id: int):
    """Bookmark an opportunity."""
    conn = get_db()
    conn.execute(
        "INSERT INTO bookmarked (opportunity_id, bookmarked_date) VALUES (?, ?)",
        (opp_id, datetime.now().isoformat())
    )
    conn.execute("UPDATE opportunities SET status = 'bookmarked' WHERE id = ?", (opp_id,))
    conn.commit()
    conn.close()


def get_bookmarked() -> List[Dict]:
    """Get all bookmarked opportunities."""
    conn = get_db()
    rows = conn.execute("""
        SELECT o.* FROM opportunities o
        JOIN bookmarked b ON o.id = b.opportunity_id
        ORDER BY b.bookmarked_date DESC
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def log_scan(sources: str, items_found: int, opportunities_added: int, duration: float):
    """Log a completed scan."""
    conn = get_db()
    conn.execute("""
        INSERT INTO scan_log (scan_date, sources_scanned, items_found, opportunities_added, duration_seconds)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), sources, items_found, opportunities_added, duration))
    conn.commit()
    conn.close()


def log_email(opportunity_count: int, subject: str):
    """Log a sent email."""
    conn = get_db()
    conn.execute("""
        INSERT INTO email_log (sent_date, opportunity_count, subject)
        VALUES (?, ?, ?)
    """, (datetime.now().isoformat(), opportunity_count, subject))
    conn.commit()
    conn.close()


def get_scan_history(limit: int = 10) -> List[Dict]:
    """Get recent scan history."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM scan_log ORDER BY scan_date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stats() -> Dict:
    """Get dashboard stats."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM opportunities").fetchone()['c']
    new = conn.execute("SELECT COUNT(*) as c FROM opportunities WHERE status = 'new'").fetchone()['c']
    bookmarked = conn.execute("SELECT COUNT(*) as c FROM bookmarked").fetchone()['c']
    dismissed = conn.execute("SELECT COUNT(*) as c FROM dismissed").fetchone()['c']
    scans = conn.execute("SELECT COUNT(*) as c FROM scan_log").fetchone()['c']
    last_scan = conn.execute("SELECT scan_date FROM scan_log ORDER BY scan_date DESC LIMIT 1").fetchone()
    conn.close()
    return {
        'total': total,
        'new': new,
        'bookmarked': bookmarked,
        'dismissed': dismissed,
        'scans': scans,
        'last_scan': last_scan['scan_date'] if last_scan else 'Never'
    }
