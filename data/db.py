"""
SQLite Storage Layer for Portin

Provides crash-resistant storage for:
- Discovery sessions
- Companies (discovered + enriched)
- Progress checkpoints

Replaces JSON file storage with queryable SQLite.
"""

import sqlite3
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager


def extract_company_terms(name: str) -> set:
    """
    Extract all meaningful terms from a company name, including parenthetical content.
    Returns a set of lowercase terms for comparison.
    
    Example: "GCMMF (Amul)" -> {'gcmmf', 'amul'}
            "Gujarat Cooperative Milk Marketing Federation (GCMMF)" -> {'gujarat', 'cooperative', 'marketing', 'federation', 'gcmmf'}
    """
    if not name:
        return set()
    
    n = name.lower().strip()
    
    # Extract content from parentheses separately
    parens = re.findall(r'\(([^)]+)\)', n)
    
    # Remove common suffixes/noise words
    noise_words = {
        'private', 'pvt', 'limited', 'ltd', 'inc', 'incorporated', 'corp', 
        'corporation', 'llc', 'llp', 'co', 'company', 'the', 'of', 'and',
        'products', 'product', 'industries', 'industry', 'enterprises',
        'enterprise', 'foods', 'food', 'dairy', 'milk', 'brand', 'state',
        'cooperative', 'federation', 'union', 'marketing', 'producers'
    }
    
    # Get all words from the name (including from parentheses)
    all_text = n + ' ' + ' '.join(parens)
    
    # Extract words, remove special chars
    words = re.findall(r'[a-z0-9]+', all_text)
    
    # Filter out noise words and very short terms
    terms = {w for w in words if w not in noise_words and len(w) >= 3}
    
    return terms


def normalize_company_name(name: str) -> str:
    """
    Normalize company name for duplicate detection.
    Returns the most distinctive term(s) from the company name.
    """
    terms = extract_company_terms(name)
    if not terms:
        return ""
    
    # Sort by length descending (longer terms are usually more distinctive)
    return ' '.join(sorted(terms, key=lambda x: -len(x)))


def is_similar_company(name1: str, name2: str) -> bool:
    """
    Check if two company names are similar enough to be duplicates.
    Uses term overlap - if they share any significant term, they're likely the same.
    
    Examples:
    - "Amul" vs "GCMMF (Amul)" -> True (share 'amul')
    - "Amul" vs "Gujarat Cooperative Milk Marketing Federation (GCMMF)" -> True (if GCMMF matches)
    - "Mother Dairy" vs "Amul" -> False (no shared terms)
    """
    terms1 = extract_company_terms(name1)
    terms2 = extract_company_terms(name2)
    
    if not terms1 or not terms2:
        return False
    
    # Check for shared terms
    shared = terms1 & terms2
    
    if shared:
        # If they share any term of 4+ characters, consider them duplicates
        for term in shared:
            if len(term) >= 4:
                return True
    
    # Also check if the normalized names are contained in each other
    n1 = normalize_company_name(name1)
    n2 = normalize_company_name(name2)
    
    if n1 and n2:
        # Check if shortest meaningful term appears in the other
        short_terms1 = [t for t in terms1 if len(t) >= 4]
        short_terms2 = [t for t in terms2 if len(t) >= 4]
        
        for t1 in short_terms1:
            if t1 in n2:
                return True
        for t2 in short_terms2:
            if t2 in n1:
                return True
    
    return False


# Default database path - in the database/ directory
# Get project root (parent of data/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_DIR = os.path.join(_PROJECT_ROOT, "database")
os.makedirs(_DB_DIR, exist_ok=True)
DB_PATH = os.path.join(_DB_DIR, "portin.db")


@contextmanager
def get_db_connection(db_path: str = DB_PATH):
    """Context manager for database connections."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(db_path: str = DB_PATH):
    """Initialize database with required tables."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Sessions table - tracks discovery runs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                status TEXT NOT NULL DEFAULT 'active',
                criteria_json TEXT,
                config_json TEXT,
                notes TEXT
            )
        """)
        
        # Companies table - discovered + enriched companies
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                name TEXT NOT NULL,
                domain TEXT,
                website TEXT,
                source TEXT,
                discovered_at TEXT NOT NULL DEFAULT (datetime('now')),
                enriched_at TEXT,
                status TEXT NOT NULL DEFAULT 'discovered',
                score REAL,
                priority TEXT,
                raw_data_json TEXT,
                enriched_data_json TEXT,
                verified_claims_json TEXT,
                citations_json TEXT,
                research_grade TEXT,
                hallucination_risk_score REAL,
                apollo_data_json TEXT,
                research_completed_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                UNIQUE(session_id, name)
            )
        """)
        
        # Checkpoints table - for crash recovery
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                checkpoint_type TEXT NOT NULL,
                checkpoint_key TEXT NOT NULL,
                checkpoint_data_json TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                UNIQUE(session_id, checkpoint_type, checkpoint_key)
            )
        """)
        
        # Scraped URLs table - to avoid re-scraping same pages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scraped_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
                companies_found INTEGER DEFAULT 0,
                status TEXT DEFAULT 'scraped'
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_session ON companies(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_urls ON scraped_urls(url)")
        
        
        # Helper for migration
        def _add_column(cur, table, col_def):
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                print(f"[DB] Added column {col_def} to {table}")
            except Exception:
                pass # Column likely exists

        # Migration: Add new Deep Research columns to existing table
        _add_column(cursor, "companies", "verified_claims_json TEXT")
        _add_column(cursor, "companies", "citations_json TEXT")
        _add_column(cursor, "companies", "research_grade TEXT")
        _add_column(cursor, "companies", "hallucination_risk_score REAL")
        _add_column(cursor, "companies", "apollo_data_json TEXT")
        _add_column(cursor, "companies", "research_completed_at TEXT")

        print(f"[DB] Database initialized at {db_path}")


# ─────────────────────────────────────────────────────────────
# SESSION OPERATIONS
# ─────────────────────────────────────────────────────────────

def create_session(criteria: Dict, config: Dict = None, db_path: str = DB_PATH) -> int:
    """Create a new discovery session. Returns session_id."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (criteria_json, config_json, status)
            VALUES (?, ?, 'active')
        """, (json.dumps(criteria), json.dumps(config or {})))
        
        session_id = cursor.lastrowid
        print(f"[DB] Created session {session_id}")
        return session_id


def get_session(session_id: int, db_path: str = DB_PATH) -> Optional[Dict]:
    """Get session by ID."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        
        if row:
            return {
                "id": row["id"],
                "created_at": row["created_at"],
                "status": row["status"],
                "criteria": json.loads(row["criteria_json"]) if row["criteria_json"] else {},
                "config": json.loads(row["config_json"]) if row["config_json"] else {},
                "notes": row["notes"]
            }
        return None


def get_latest_session(db_path: str = DB_PATH) -> Optional[Dict]:
    """Get the most recent session."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            return get_session(row["id"], db_path)
        return None


def update_session_status(session_id: int, status: str, db_path: str = DB_PATH):
    """Update session status (active, completed, failed)."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions SET status = ? WHERE id = ?
        """, (status, session_id))


def update_session_criteria(session_id: int, criteria: Dict, db_path: str = DB_PATH):
    """Update session criteria (for recycling empty sessions)."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions SET criteria_json = ?, created_at = datetime('now')
            WHERE id = ?
        """, (json.dumps(criteria), session_id))


def merge_sessions(source_ids: list, target_id: int, db_path: str = DB_PATH):
    """Merge multiple source sessions into a target session."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Move companies to target session
        placeholders = ','.join(['?'] * len(source_ids))
        cursor.execute(f"""
            UPDATE companies 
            SET session_id = ? 
            WHERE session_id IN ({placeholders})
        """, [target_id] + source_ids)
        
        # 2. Delete source sessions
        cursor.execute(f"""
            DELETE FROM sessions 
            WHERE id IN ({placeholders})
        """, source_ids)

        return True


def get_all_sessions(db_path: str = DB_PATH) -> List[Dict]:
    """
    Get all sessions with summary info including industry tag.
    Returns list of sessions with company counts and industry extracted from criteria.
    """
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Get all sessions
        cursor.execute("""
            SELECT 
                s.id,
                s.created_at,
                s.status,
                s.criteria_json,
                COUNT(c.id) as company_count,
                SUM(CASE WHEN c.status = 'enriched' THEN 1 ELSE 0 END) as enriched_count,
                SUM(CASE WHEN c.status = 'discovered' THEN 1 ELSE 0 END) as discovered_count
            FROM sessions s
            LEFT JOIN companies c ON c.session_id = s.id
            GROUP BY s.id
            ORDER BY s.id DESC
        """)
        
        sessions = []
        for row in cursor.fetchall():
            # Extract industry from criteria
            industry = "Unknown"
            if row["criteria_json"]:
                try:
                    criteria = json.loads(row["criteria_json"])
                    # Try to get industry from criteria
                    ind = criteria.get("industry", {})
                    industries = ind.get("industry", [])
                    if industries:
                        industry = industries[0]  # Primary industry
                    elif ind.get("keywords"):
                        industry = ind.get("keywords", ["Unknown"])[0]
                except:
                    pass
            
            sessions.append({
                "id": row["id"],
                "created_at": row["created_at"],
                "status": row["status"],
                "industry": industry,
                "company_count": row["company_count"] or 0,
                "enriched_count": row["enriched_count"] or 0,
                "discovered_count": row["discovered_count"] or 0,
            })
        
        return sessions


def get_companies_by_session(
    session_id: int,
    status: str = None,
    db_path: str = DB_PATH
) -> List[Dict]:
    """Get companies for a specific session."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM companies WHERE session_id = ?"
        params = [session_id]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY score DESC NULLS LAST"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# ─────────────────────────────────────────────────────────────
# COMPANY OPERATIONS
# ─────────────────────────────────────────────────────────────

def add_company(
    session_id: int,
    name: str,
    domain: str = None,
    website: str = None,
    source: str = "unknown",
    score: float = None,
    raw_data: Dict = None,
    db_path: str = DB_PATH,
    skip_similarity_check: bool = False
) -> Optional[int]:
    """
    Add a discovered company. Returns company_id or None if duplicate.
    
    Uses fuzzy matching to detect similar company names within the same session.
    Set skip_similarity_check=True for exact-match-only behavior.
    """
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Check for similar companies in this session (unless skipped)
        if not skip_similarity_check:
            cursor.execute("""
                SELECT id, name FROM companies WHERE session_id = ?
            """, (session_id,))
            
            existing = cursor.fetchall()
            normalized_new = normalize_company_name(name)
            
            for row in existing:
                if is_similar_company(name, row['name']):
                    # Similar company already exists - skip
                    return None
        
        try:
            cursor.execute("""
                INSERT INTO companies (session_id, name, domain, website, source, score, raw_data_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'discovered')
            """, (session_id, name, domain, website, source, score, json.dumps(raw_data or {})))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Exact duplicate company name in this session
            return None


def add_companies_batch(
    session_id: int,
    companies: List[Dict],
    source: str = "unknown",
    db_path: str = DB_PATH
) -> int:
    """Add multiple companies at once. Returns count of added."""
    
    added = 0
    for company in companies:
        name = company.get("name", "").strip()
        if not name:
            continue
        
        # Get score - try multiple field names
        score = company.get("score") or company.get("fit_score")
            
        result = add_company(
            session_id=session_id,
            name=name,
            domain=company.get("domain"),
            website=company.get("website") or company.get("source_url"),
            source=source,
            score=score,
            raw_data=company,
            db_path=db_path
        )
        if result:
            added += 1
    
    return added


def get_companies(
    session_id: int,
    status: str = None,
    limit: int = None,
    db_path: str = DB_PATH
) -> List[Dict]:
    """Get companies for a session, optionally filtered by status."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM companies WHERE session_id = ?"
        params = [session_id]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY id"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        
        return [dict(row) for row in cursor.fetchall()]


def get_companies_to_enrich(session_id: int, limit: int = 50, db_path: str = DB_PATH) -> List[Dict]:
    """Get companies that haven't been enriched yet."""
    return get_companies(session_id, status="discovered", limit=limit, db_path=db_path)


def update_company_enrichment(
    company_id: int,
    enriched_data: Dict,
    score: float = None,
    priority: str = None,
    db_path: str = DB_PATH
):
    """Update a company with enrichment data."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE companies
            SET enriched_at = datetime('now'),
                status = 'enriched',
                enriched_data_json = ?,
                score = ?,
                priority = ?
            WHERE id = ?
        """, (json.dumps(enriched_data), score, priority, company_id))


def mark_company_failed(company_id: int, error: str = None, db_path: str = DB_PATH):
    """Mark a company as failed to enrich."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE companies
            SET status = 'failed',
                raw_data_json = json_set(COALESCE(raw_data_json, '{}'), '$.error', ?)
            WHERE id = ?
        """, (error, company_id))


def get_enriched_companies(session_id: int, db_path: str = DB_PATH) -> List[Dict]:
    """Get all enriched companies with their data."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, domain, website, source, score, priority, enriched_data_json
            FROM companies
            WHERE session_id = ? AND status = 'enriched'
            ORDER BY score DESC NULLS LAST
        """, (session_id,))
        
        results = []
        for row in cursor.fetchall():
            data = {
                "id": row["id"],
                "name": row["name"],
                "domain": row["domain"],
                "website": row["website"],
                "source": row["source"],
                "score": row["score"],
                "priority": row["priority"],
            }
            # Merge enriched data
            if row["enriched_data_json"]:
                data.update(json.loads(row["enriched_data_json"]))
            results.append(data)
        
        return results


# ─────────────────────────────────────────────────────────────
# CHECKPOINT OPERATIONS (for crash recovery)
# ─────────────────────────────────────────────────────────────

def save_checkpoint(
    session_id: int,
    checkpoint_type: str,
    checkpoint_key: str,
    data: Any = None,
    db_path: str = DB_PATH
):
    """Save a checkpoint for crash recovery."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO checkpoints (session_id, checkpoint_type, checkpoint_key, checkpoint_data_json)
            VALUES (?, ?, ?, ?)
        """, (session_id, checkpoint_type, checkpoint_key, json.dumps(data)))


def get_checkpoint(
    session_id: int,
    checkpoint_type: str,
    checkpoint_key: str,
    db_path: str = DB_PATH
) -> Optional[Any]:
    """Get a checkpoint value."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT checkpoint_data_json FROM checkpoints
            WHERE session_id = ? AND checkpoint_type = ? AND checkpoint_key = ?
        """, (session_id, checkpoint_type, checkpoint_key))
        
        row = cursor.fetchone()
        if row and row["checkpoint_data_json"]:
            return json.loads(row["checkpoint_data_json"])
        return None


def has_checkpoint(
    session_id: int,
    checkpoint_type: str,
    checkpoint_key: str,
    db_path: str = DB_PATH
) -> bool:
    """Check if a checkpoint exists."""
    return get_checkpoint(session_id, checkpoint_type, checkpoint_key, db_path) is not None


def get_all_checkpoints(session_id: int, checkpoint_type: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Get all checkpoints of a type for a session."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT checkpoint_key, checkpoint_data_json FROM checkpoints
            WHERE session_id = ? AND checkpoint_type = ?
        """, (session_id, checkpoint_type))
        
        return {
            row["checkpoint_key"]: json.loads(row["checkpoint_data_json"]) if row["checkpoint_data_json"] else None
            for row in cursor.fetchall()
        }


# ─────────────────────────────────────────────────────────────
# STATISTICS
# ─────────────────────────────────────────────────────────────

def get_session_stats(session_id: int, db_path: str = DB_PATH) -> Dict:
    """Get statistics for a session."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM companies
            WHERE session_id = ?
            GROUP BY status
        """, (session_id,))
        
        status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "total": sum(status_counts.values()),
            "discovered": status_counts.get("discovered", 0),
            "enriched": status_counts.get("enriched", 0),
            "failed": status_counts.get("failed", 0),
        }


# ─────────────────────────────────────────────────────────────
# GLOBAL DEDUPLICATION (ACROSS ALL SESSIONS)
# ─────────────────────────────────────────────────────────────

def get_all_known_companies(db_path: str = DB_PATH) -> List[Dict]:
    """
    Get ALL known companies across all sessions.
    Used for deduplication before searching.
    """
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT 
                name, 
                domain, 
                website,
                source,
                MAX(score) as best_score,
                MAX(enriched_at) as last_enriched
            FROM companies
            GROUP BY LOWER(name)
            ORDER BY best_score DESC NULLS LAST
        """)
        
        return [dict(row) for row in cursor.fetchall()]


def get_known_company_names(db_path: str = DB_PATH) -> set:
    """
    Get set of all known company names (lowercase for matching).
    Fast lookup for deduplication.
    """
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT LOWER(name) FROM companies")
        
        return {row[0] for row in cursor.fetchall()}


def company_exists(name: str, db_path: str = DB_PATH) -> bool:
    """Check if a company already exists in the database."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM companies WHERE LOWER(name) = ? LIMIT 1",
            (name.lower().strip(),)
        )
        return cursor.fetchone() is not None


def get_company_by_name(name: str, db_path: str = DB_PATH) -> Optional[Dict]:
    """Get a company by name (case-insensitive)."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM companies WHERE LOWER(name) = ? ORDER BY score DESC LIMIT 1",
            (name.lower().strip(),)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def filter_new_companies(companies: List[Dict], db_path: str = DB_PATH) -> List[Dict]:
    """
    Filter out companies that already exist in the database.
    Returns only NEW companies that haven't been discovered before.
    """
    
    known_names = get_known_company_names(db_path)
    
    new_companies = []
    skipped = 0
    
    for company in companies:
        name = company.get("name", "").strip().lower()
        if name and name not in known_names:
            new_companies.append(company)
        else:
            skipped += 1
    
    if skipped > 0:
        print(f"[DB] Skipped {skipped} already-known companies")
    
    return new_companies


def get_database_stats(db_path: str = DB_PATH) -> Dict:
    """Get overall database statistics."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Total companies
        cursor.execute("SELECT COUNT(*) FROM companies")
        total_companies = cursor.fetchone()[0]
        
        # By status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM companies
            GROUP BY status
        """)
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Total sessions
        cursor.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cursor.fetchone()[0]
        
        # Unique companies (by name)
        cursor.execute("SELECT COUNT(DISTINCT LOWER(name)) FROM companies")
        unique_companies = cursor.fetchone()[0]
        
        return {
            "total_companies": total_companies,
            "unique_companies": unique_companies,
            "total_sessions": total_sessions,
            "discovered": by_status.get("discovered", 0),
            "enriched": by_status.get("enriched", 0),
            "failed": by_status.get("failed", 0),
        }


# ─────────────────────────────────────────────────────────────
# URL CACHING (Avoid re-scraping)
# ─────────────────────────────────────────────────────────────

def get_scraped_urls(db_path: str = DB_PATH) -> set:
    """Get set of all URLs that have been scraped."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM scraped_urls")
        
        return {row[0] for row in cursor.fetchall()}


def is_url_scraped(url: str, db_path: str = DB_PATH) -> bool:
    """Check if a URL has already been scraped."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM scraped_urls WHERE url = ? LIMIT 1", (url,))
        
        return cursor.fetchone() is not None


def mark_url_scraped(url: str, companies_found: int = 0, db_path: str = DB_PATH):
    """Mark a URL as scraped."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO scraped_urls (url, companies_found) VALUES (?, ?)",
                (url, companies_found)
            )
        except Exception:
            pass  # Ignore duplicates


def filter_new_urls(urls: List[str], db_path: str = DB_PATH) -> List[str]:
    """Filter out URLs that have already been scraped."""
    
    scraped = get_scraped_urls(db_path)
    
    new_urls = [url for url in urls if url not in scraped]
    skipped = len(urls) - len(new_urls)
    
    if skipped > 0:
        print(f"[DB] Skipped {skipped} already-scraped URLs")
    
    return new_urls


def get_scraped_url_stats(db_path: str = DB_PATH) -> Dict:
    """Get statistics about scraped URLs."""
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM scraped_urls")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(companies_found) FROM scraped_urls")
        companies = cursor.fetchone()[0] or 0
        
        return {"total_urls_scraped": total, "total_companies_from_scraping": companies}


# ─────────────────────────────────────────────────────────────
# MIGRATION FROM JSON FILES
# ─────────────────────────────────────────────────────────────

def import_from_json(
    criteria_file: str,
    companies_file: str,
    db_path: str = DB_PATH
) -> int:
    """Import existing JSON data into SQLite. Returns session_id."""
    
    # Load criteria
    criteria = {}
    if os.path.exists(criteria_file):
        with open(criteria_file, 'r') as f:
            criteria = json.load(f)
    
    # Create session
    session_id = create_session(criteria, db_path=db_path)
    
    # Load companies
    if os.path.exists(companies_file):
        with open(companies_file, 'r') as f:
            companies = json.load(f)
        
        added = add_companies_batch(session_id, companies, source="json_import", db_path=db_path)
        print(f"[DB] Imported {added} companies from {companies_file}")
    
    return session_id


# Initialize database when module is imported
if not os.path.exists(DB_PATH):
    init_database()
