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

# Global log store for real-time streaming
SESSION_LOGS = {}

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
        
        # Setup logging
        SESSION_LOGS[session_id] = []
        def log_callback(msg):
            ts = datetime.now().strftime("%H:%M:%S")
            SESSION_LOGS[session_id].append(f"<span class='log-time'>{ts}</span> {msg}")
            
        engine.log_callback = log_callback
        
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
    
    # 1. Process with Porto (Research Consultant)
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
    # Note: Auto-enrich is available via button click, not on initial load
    return render_template('partials/step_discovery.html', 
                         session_id=session_id, 
                         criteria=criteria)

def save_criteria_to_json(criteria):
    """Sync criteria to output/search_criteria.json for consistency."""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_root, 'output')
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, 'search_criteria.json')
        
        with open(filepath, 'w') as f:
            json.dump(criteria, f, indent=4)
        print(f"[Sync] Saved criteria to {filepath}")
    except Exception as e:
        print(f"[Sync] Failed to save criteria to JSON: {e}")

@app.route('/pipeline/enrich-reference', methods=['POST'])
def enrich_reference():
    """Step 2b: Auto-enrich keywords from reference companies."""
    session_id = request.form.get('session_id')
    refs_str = request.form.get('reference_companies', '')
    
    session = get_session(session_id)
    if not session:
        return "Session not found", 404
    criteria = session['criteria']
    
    # Parse references
    refs = [r.strip() for r in refs_str.split(',') if r.strip()]
    if refs:
        # Update references in criteria
        criteria['industry']['reference_companies'] = refs
        
        # Init engine to access profiling logic
        engine = AggressiveDiscoveryEngine(criteria)
        
        # Run profiling (updates engine.enhanced_keywords)
        # Note: We need to capture logs for this too? For now, just run it.
        # It prints to stdout, which is fine.
        engine._profile_reference_companies(refs)
        
        # Merge new keywords
        current_kws = set(criteria['industry'].get('keywords', []))
        if engine.enhanced_keywords:
            for kw in engine.enhanced_keywords:
                current_kws.add(kw)
            criteria['industry']['keywords'] = list(current_kws)
            
        # Save updates to DB
        update_session_criteria(session_id, criteria)
        
        # Sync to JSON file
        save_criteria_to_json(criteria)
        
    return render_template('partials/step_discovery.html', 
                         session_id=session_id, 
                         criteria=criteria,
                         enriched_keywords=engine.enhanced_keywords if 'engine' in locals() and engine.enhanced_keywords else [])

@app.route('/pipeline/update-criteria', methods=['POST'])
def update_criteria_route():
    """Step 2c: Manual criteria update."""
    session_id = request.form.get('session_id')
    session = get_session(session_id)
    if not session:
        return "Session not found", 404
        
    criteria = session['criteria']
    
    # Update fields from form
    criteria['industry']['keywords'] = [k.strip() for k in request.form.get('keywords', '').split(',') if k.strip()]
    criteria['industry']['reference_companies'] = [r.strip() for r in request.form.get('reference_companies', '').split(',') if r.strip()]
    
    # New: Additional Context
    criteria['additional_context'] = request.form.get('additional_context', '').strip()
    
    try:
        criteria['revenue']['revenue_min_millions'] = int(request.form.get('revenue_min', 0))
        criteria['revenue']['revenue_max_millions'] = int(request.form.get('revenue_max', 1000))
    except (ValueError, TypeError):
        pass
    
    # Save to DB
    update_session_criteria(session_id, criteria)
    
    # Sync to JSON file
    save_criteria_to_json(criteria)
    
    return render_template('partials/step_discovery.html', 
                         session_id=session_id, 
                         criteria=criteria)

@app.route('/pipeline/start-discovery', methods=['POST'])
def start_discovery():
    """Handle Step 2: Start Discovery."""
    session_id = int(request.form.get('session_id'))
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

@app.route('/pipeline/logs')
def get_logs():
    """Get real-time logs for a session."""
    session_id = request.args.get('session_id')
    try:
        session_id = int(session_id)
        logs = SESSION_LOGS.get(session_id, [])
        # Return only last 8 lines for clean UI
        return "".join([f"<div class='log-line'>{l}</div>" for l in logs[-8:]])
    except:
        return ""

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

@app.route('/clear-session/<int:session_id>')
def clear_session(session_id):
    """Clear all companies from a specific session."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM companies WHERE session_id = ?", (session_id,))
    flash(f"Session #{session_id} cleared successfully", "success")
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

@app.route('/export/csv')
def export_csv():
    """Export companies as CSV."""
    import csv
    import io
    
    session_filter = request.args.get('session', 'all')
    
    # Build query
    query = "SELECT * FROM companies WHERE 1=1"
    params = []
    
    if session_filter != 'all':
        try:
            query += " AND session_id = ?"
            params.append(int(session_filter))
        except ValueError:
            pass
    
    query += " ORDER BY score DESC"
    
    # Get companies
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Name', 'Domain', 'Website', 'Score', 'Status', 'Session ID', 'Source'])
    
    # Data
    for row in rows:
        c = dict(row)
        writer.writerow([
            c.get('name', ''),
            c.get('domain', ''),
            c.get('website', ''),
            c.get('score', ''),
            c.get('status', ''),
            c.get('session_id', ''),
            c.get('source', '')
        ])
    
    # Return as download
    from flask import Response
    output.seek(0)
    filename = f"portin_export_session_{session_filter}.csv" if session_filter != 'all' else "portin_export_all.csv"
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

if __name__ == '__main__':
    print("Starting Portin Dashboard (Glassmorphism Edition)...")
    print("Open http://localhost:5000")
    app.run(debug=True, port=5000)
