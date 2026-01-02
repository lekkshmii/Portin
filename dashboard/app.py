import os
import sys
import json
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime

# Add project root to path to import modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from data.db import (
    get_db_connection, DB_PATH, get_database_stats, get_all_sessions, 
    get_companies, init_database, create_session, get_session, update_session_status,
    get_latest_session, update_session_criteria, merge_sessions
)
from intake.lead_researcher import AIResearchConsultant
from discovery.engine import AggressiveDiscoveryEngine
import threading
import time

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)
app.secret_key = 'portin_dashboard_secret_key'

# Initialize DB
init_database()

# Helper background task
def run_discovery_bg(session_id, criteria, engine_type):
    """Run discovery in a separate thread."""
    try:
        print(f"Starting discovery for session {session_id} in background...")
        update_session_status(session_id, "running")
        
        # Init engine
        engine = AggressiveDiscoveryEngine(criteria)
        engine.session_id = session_id
        engine.search_engine = engine_type
        
        # Run
        companies = engine.discover_all_sources()
        
        # Save results (JSON + DB)
        engine.save_results(companies)
        
        # Update status
        update_session_status(session_id, "completed")
        print(f"Discovery finished for session {session_id}")
        
    except Exception as e:
        print(f"Discovery failed: {e}")
        update_session_status(session_id, "failed")

# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Main dashboard view - Company List."""
    
    # Get filters
    session_filter = request.args.get('session', 'all')
    status_filter = request.args.get('status', 'all')
    min_score = int(request.args.get('min_score', 0))
    sort_by = request.args.get('sort', 'score_desc')
    
    # Get stats & sessions for sidebar/header
    stats = get_database_stats()
    sessions = get_all_sessions()
    
    # Build query for companies
    companies = []
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM companies WHERE 1=1"
        params = []
        
        if session_filter != 'all':
            query += " AND session_id = ?"
            params.append(int(session_filter))
            
        if status_filter != 'all':
            query += " AND status = ?"
            params.append(status_filter)
            
        if min_score > 0:
            query += " AND score >= ?"
            params.append(min_score)
            
        # Sorting
        sort_map = {
            'score_desc': "ORDER BY score DESC NULLS LAST",
            'score_asc': "ORDER BY score ASC NULLS LAST",
            'name_asc': "ORDER BY name ASC",
            'name_desc': "ORDER BY name DESC",
            'session_desc': "ORDER BY session_id DESC",
            'session_asc': "ORDER BY session_id ASC"
        }
        query += " " + sort_map.get(sort_by, sort_map['score_desc'])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Process rows
        for row in rows:
            c = dict(row)
            if c.get('raw_data_json'):
                try:
                    raw = json.loads(c['raw_data_json'])
                    c['location'] = raw.get('location', raw.get('headquarters', ''))
                    c['info'] = raw.get('info', raw.get('description', ''))[:100]
                except: pass
            companies.append(c)

    return render_template(
        'index.html',
        companies=companies,
        stats=stats,
        sessions=sessions,
        filters={
            'session': session_filter,
            'status': status_filter,
            'min_score': min_score,
            'sort': sort_by
        }
    )

@app.route('/pipeline')
def pipeline():
    return render_template('pipeline.html')

@app.route('/pipeline/intake', methods=['POST'])
def pipeline_intake():
    """Handle Step 1: Intake Form."""
    form_data = request.form.to_dict()
    
    # 1. Process with AI Consultant
    consultant = AIResearchConsultant()
    criteria = consultant.process_form_inputs(form_data)
    
    # 2. Recycle or Create Session
    session_id = None
    
    # Check if latest session is empty/abandoned
    try:
        latest = get_latest_session()
        if latest and latest['status'] != 'running':
            # Check company count
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM companies WHERE session_id = ?", (latest['id'],))
                count = cursor.fetchone()[0]
            
            if count == 0:
                # Recycle!
                session_id = latest['id']
                update_session_criteria(session_id, criteria)
                update_session_status(session_id, 'active')
                print(f"Recycled empty session {session_id}")
    except Exception as e:
        print(f"Recycling check failed: {e}")

    if not session_id:
        session_id = create_session(criteria=criteria)
    
    # 3. Render Step 2 (Discovery UI)
    return render_template('partials/step_discovery.html', 
                         session_id=session_id, 
                         criteria=criteria)

@app.route('/pipeline/start-discovery', methods=['POST'])
def start_discovery():
    """Handle Step 2: Start Discovery."""
    session_id = request.form.get('session_id')
    engine_type = request.form.get('engine', 'grounding')
    
    # Get session details to retrieve criteria
    try:
        session = get_session(session_id)
        if not session:
            return "Session not found", 404
            
        # Criteria is already parsed by get_session
        criteria = session['criteria']
        
        # Start background thread
        thread = threading.Thread(
            target=run_discovery_bg,
            args=(session_id, criteria, engine_type)
        )
        thread.daemon = True
        thread.start()
        
        # Render Step 3 (Progress) immediately
        return render_template('partials/step_progress.html', 
                             session_id=session_id,
                             companies_found=0,
                             status='running')
                             
    except Exception as e:
        return f'<div class="alert alert-danger">Error starting discovery: {e}</div>'

@app.route('/pipeline/status')
def pipeline_status():
    """Poll for discovery progress."""
    session_id = request.args.get('session_id')
    
    # Get Session Status
    session = get_session(session_id)
    if not session:
        return ""
        
    status = session['status']
    
    # Get Company Count
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM companies WHERE session_id = ?", (session_id,))
        count = cursor.fetchone()[0]
    
    if status == 'completed':
        # Swap to Step 4 (Enrichment Setup)
        return render_template('partials/step_enrichment.html',
                              session_id=session_id,
                              companies_count=count)
    else:
        # Keep updating progress
        return render_template('partials/step_progress.html',
                             session_id=session_id,
                             companies_found=count,
                             status=status)

@app.route('/discovery')
def discovery():
    """Discovery Control Page."""
    return render_template('discovery.html')

@app.route('/settings')
def settings():
    """Settings Page."""
    sessions = get_all_sessions()
    return render_template('settings.html', sessions=sessions)

@app.route('/settings/merge', methods=['POST'])
def merge_sessions_route():
    """Handle session merging."""
    target_id = request.form.get('target_id')
    source_ids = request.form.getlist('source_ids')
    
    if not target_id or not source_ids:
        flash("Please select sessions to merge", "error")
        return redirect(url_for('settings'))
        
    try:
        # Convert to ints
        target_id = int(target_id)
        source_ids = [int(sid) for sid in source_ids if int(sid) != target_id]
        
        if not source_ids:
            flash("No valid source sessions selected", "warning")
            return redirect(url_for('settings'))
            
        merge_sessions(source_ids, target_id)
        flash(f"Merged {len(source_ids)} sessions into Session #{target_id}", "success")
        
    except Exception as e:
        flash(f"Merge failed: {e}", "danger")
        
    return redirect(url_for('settings'))

@app.route('/delete/<int:company_id>')
def delete_company(company_id):
    """Delete a company."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    flash(f"Company {company_id} deleted", "success")
    return redirect(url_for('index'))

@app.route('/clear')
def clear_db():
    """Clear entire database."""
    # This should be a POST ideally, but GET for simple prototype link
    with get_db_connection() as conn:
        conn.execute("DELETE FROM companies")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM checkpoints")
        conn.execute("DELETE FROM sqlite_sequence") # Reset auto-increment
    flash("Database cleared successfully", "success")
    return redirect(url_for('index'))

@app.route('/api/stats')
def api_stats():
    """JSON API for stats (for auto-refresh)."""
    return jsonify(get_database_stats())

if __name__ == '__main__':
    print("Starting Portin Dashboard (Glassmorphism Edition)...")
    print("Open http://localhost:5000")
    app.run(debug=True, port=5000)
