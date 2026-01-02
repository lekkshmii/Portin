#!/usr/bin/env python3
"""
Portin CLI - M&A Target Discovery System
Clean command-line interface for managing discovery sessions, database, and pipeline operations.
"""

import os
import sys
import argparse
import json
from datetime import datetime
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from data.db import (
    init_database, get_all_sessions, get_session, create_session,
    get_companies_by_session, get_session_stats, get_database_stats,
    get_enriched_companies, DB_PATH, update_session_status,
    get_companies_to_enrich, mark_company_failed, get_all_known_companies
)


class PortinCLI:
    """Main CLI controller"""

    def __init__(self):
        self.parser = self._setup_parser()

    def _setup_parser(self):
        parser = argparse.ArgumentParser(
            description='Portin - M&A Target Discovery System',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog='''
Examples:
  python3 portin.py status                        Show system overview
  python3 portin.py run intake                    Start Porto interview
  python3 portin.py run discovery                 Find companies
  python3 portin.py sessions list                 List all sessions
  python3 portin.py sessions show --id 3          View session details
  python3 portin.py companies list --session 3    List companies
  python3 portin.py db backup                     Backup database
  python3 portin.py guide                         Show detailed usage guide

Workflow:
  1. python3 portin.py run intake       (Interview with Porto)
  2. python3 portin.py run discovery    (Find companies)
  3. python3 portin.py run enrichment   (Enrich data)
  4. python3 portin.py sessions show --id N  (Review results)
            '''
        )

        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        subparsers.add_parser('init', help='Initialize database')
        subparsers.add_parser('status', help='Show system status and recent activity')
        subparsers.add_parser('guide', help='Show detailed usage guide with examples')

        run_parser = subparsers.add_parser('run', help='Run pipeline operations')
        run_parser.add_argument('phase', choices=['intake', 'discovery', 'enrichment', 'pipeline', 'dashboard'],
                               help='Phase: intake, discovery, enrichment, pipeline, dashboard')
        run_parser.add_argument('--session', type=int, help='Session ID (for discovery/enrichment)')

        session_parser = subparsers.add_parser('sessions', help='Manage discovery sessions')
        session_parser.add_argument('action', choices=['list', 'show', 'create', 'archive'],
                                   help='Action: list, show, create, archive')
        session_parser.add_argument('--id', type=int, help='Session ID')
        session_parser.add_argument('--criteria', type=str, help='Path to criteria JSON file')

        db_parser = subparsers.add_parser('db', help='Database management')
        db_parser.add_argument('action', choices=['stats', 'export', 'backup', 'clean', 'companies'],
                              help='Action: stats, export, backup, clean, companies')
        db_parser.add_argument('--session', type=int, help='Session ID filter')
        db_parser.add_argument('--output', type=str, help='Output file path')
        db_parser.add_argument('--status', choices=['discovered', 'enriched', 'failed'],
                              help='Filter by company status')

        companies_parser = subparsers.add_parser('companies', help='Manage companies')
        companies_parser.add_argument('action', choices=['list', 'export'],
                                     help='Action: list, export')
        companies_parser.add_argument('--session', type=int, help='Session ID (required)')
        companies_parser.add_argument('--status', choices=['discovered', 'enriched', 'failed'],
                                     help='Filter by status')
        companies_parser.add_argument('--limit', type=int, default=50, help='Limit results (default: 50)')
        companies_parser.add_argument('--output', type=str, help='Export to file')

        return parser

    def run(self, args=None):
        args = self.parser.parse_args(args)

        if not args.command:
            self.parser.print_help()
            return

        command_map = {
            'init': self.cmd_init,
            'run': self.cmd_run,
            'sessions': self.cmd_sessions,
            'db': self.cmd_db,
            'companies': self.cmd_companies,
            'status': self.cmd_status,
            'guide': self.cmd_guide
        }

        handler = command_map.get(args.command)
        if handler:
            try:
                handler(args)
            except KeyboardInterrupt:
                print("\n\nOperation cancelled by user")
                sys.exit(0)
            except Exception as e:
                print(f"\nError: {e}")
                sys.exit(1)

    def cmd_init(self, args):
        """Initialize database"""
        print("Initializing Portin database...")
        init_database()
        print(f"Database initialized at: {DB_PATH}")
        stats = get_database_stats()
        self._print_stats(stats)

    def cmd_run(self, args):
        """Run pipeline phases"""
        import subprocess
        import time

        scripts = {
            'intake': 'run_intake.py',
            'discovery': 'run_discovery.py',
            'enrichment': 'run_enrichment.py',
            'pipeline': 'run_pipeline.py',
            'dashboard': 'run_dashboard.py'
        }

        script = scripts[args.phase]
        print(f"\nStarting {args.phase} phase...")
        print("-" * 60)

        cli_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, cli_dir)
        from progress import ProgressIndicator
        import signal

        progress = ProgressIndicator(f"{args.phase.title()} Phase")
        progress.start(f"Running {args.phase}...")

        def signal_handler(sig, frame):
            progress.stop()
            print("\n\nOperation interrupted by user")
            sys.exit(0)

        original_handler = signal.signal(signal.SIGINT, signal_handler)

        try:
            start_time = time.time()
            result = subprocess.run([sys.executable, script], cwd=PROJECT_ROOT)
            elapsed = time.time() - start_time

            progress.stop()

            if result.returncode != 0:
                print(f"\nError: {args.phase} phase failed after {elapsed:.0f}s")
                sys.exit(1)
            else:
                print(f"[OK] {args.phase} phase completed in {elapsed:.0f}s")

        finally:
            progress.stop()
            signal.signal(signal.SIGINT, original_handler)

    def cmd_sessions(self, args):
        """Manage sessions"""
        if args.action == 'list':
            self._list_sessions()
        elif args.action == 'show':
            if not args.id:
                print("Error: --id required for 'show' action")
                sys.exit(1)
            self._show_session(args.id)
        elif args.action == 'create':
            self._create_session(args.criteria)
        elif args.action == 'archive':
            if not args.id:
                print("Error: --id required for 'archive' action")
                sys.exit(1)
            self._archive_session(args.id)

    def cmd_db(self, args):
        """Database operations"""
        if args.action == 'stats':
            self._db_stats(args.session)
        elif args.action == 'export':
            self._db_export(args.session, args.output)
        elif args.action == 'backup':
            self._db_backup(args.output)
        elif args.action == 'clean':
            self._db_clean()
        elif args.action == 'companies':
            self._db_companies(args.session, args.status)

    def cmd_companies(self, args):
        """Company operations"""
        if args.action == 'list':
            self._list_companies(args.session, args.status, args.limit)
        elif args.action == 'export':
            self._export_companies(args.session, args.status, args.output)

    def cmd_status(self, args):
        """Show system status"""
        print("\nPortin System Status")
        print("=" * 60)

        stats = get_database_stats()
        self._print_stats(stats)

        print("\nRecent Sessions:")
        sessions = get_all_sessions()[:5]
        if sessions:
            for s in sessions:
                print(f"  [{s['id']}] {s['created_at'][:10]} - {s['industry']} ({s['company_count']} companies)")
        else:
            print("  No sessions found")

        print("\nDatabase:")
        print(f"  Location: {DB_PATH}")
        print(f"  Size: {self._get_file_size(DB_PATH)}")

        env_file = os.path.join(PROJECT_ROOT, '.env')
        if os.path.exists(env_file):
            print("\nAPI Keys:")
            self._check_api_keys()

    def cmd_guide(self, args):
        """Show usage guide"""
        print("""
Portin CLI Usage Guide
======================

GETTING STARTED
---------------
1. Install dependencies:      pip install -r requirements.txt
2. Initialize database:       python3 portin.py init
3. Check status:              python3 portin.py status

BASIC WORKFLOW
--------------
1. Run intake interview:      python3 portin.py run intake
2. Discover companies:        python3 portin.py run discovery
3. Enrich companies:          python3 portin.py run enrichment
4. View results:              python3 portin.py sessions show --id <ID>

Or run everything at once:    python3 portin.py run pipeline

COMMON COMMANDS
---------------
Status & Info:
  python3 portin.py status                    System overview
  python3 portin.py sessions list             List all sessions
  python3 portin.py sessions show --id 3      Session details

Pipeline Operations:
  python3 portin.py run intake                Porto interview
  python3 portin.py run discovery             Find companies
  python3 portin.py run enrichment            Enrich data
  python3 portin.py run dashboard             Launch dashboard

Company Management:
  python3 portin.py companies list --session 3                List companies
  python3 portin.py companies list --session 3 --status enriched    Filter by status
  python3 portin.py companies export --session 3              Export to JSON

Database Operations:
  python3 portin.py db stats                  Overall stats
  python3 portin.py db stats --session 3      Session stats
  python3 portin.py db companies              List all companies
  python3 portin.py db backup                 Backup database
  python3 portin.py db export                 Export to JSON
  python3 portin.py db clean                  Cleanup wizard

EXAMPLES
--------
Start new discovery for SaaS companies:
  python3 portin.py run intake
  python3 portin.py run discovery

Review session 5 results:
  python3 portin.py sessions show --id 5
  python3 portin.py companies list --session 5 --status enriched

Export enriched companies from session 5:
  python3 portin.py companies export --session 5 --status enriched --output results.json

Backup before cleanup:
  python3 portin.py db backup
  python3 portin.py db clean

TIPS
----
- Use --help on any command for details
- Session IDs are shown in 'sessions list'
- Status filters: discovered, enriched, failed
- Database located at: database/portin.db
- Exports go to: exports/ directory

For more help: python3 portin.py <command> --help
        """)


    def _list_sessions(self):
        """List all sessions"""
        sessions = get_all_sessions()

        if not sessions:
            print("No sessions found")
            return

        print(f"\nTotal Sessions: {len(sessions)}")
        print("-" * 90)
        print(f"{'ID':<5} {'Date':<12} {'Industry':<25} {'Companies':<12} {'Enriched':<10} {'Status':<10}")
        print("-" * 90)

        for s in sessions:
            print(f"{s['id']:<5} {s['created_at'][:10]:<12} {s['industry'][:24]:<25} "
                  f"{s['company_count']:<12} {s['enriched_count']:<10} {s['status']:<10}")

    def _show_session(self, session_id: int):
        """Show session details"""
        session = get_session(session_id)

        if not session:
            print(f"Session {session_id} not found")
            return

        print(f"\nSession {session_id}")
        print("=" * 60)
        print(f"Created: {session['created_at']}")
        print(f"Status: {session['status']}")

        if session.get('criteria'):
            print("\nSearch Criteria:")
            criteria = session['criteria']
            if 'industry' in criteria:
                ind = criteria['industry']
                if 'industry' in ind:
                    print(f"  Industry: {', '.join(ind['industry'])}")
                if 'keywords' in ind:
                    print(f"  Keywords: {', '.join(ind['keywords'])}")
            if 'location' in criteria:
                loc = criteria['location']
                if 'regions' in loc:
                    print(f"  Regions: {', '.join(loc['regions'])}")

        stats = get_session_stats(session_id)
        print("\nCompanies:")
        print(f"  Total: {stats['total']}")
        print(f"  Discovered: {stats['discovered']}")
        print(f"  Enriched: {stats['enriched']}")
        print(f"  Failed: {stats['failed']}")

    def _create_session(self, criteria_file: Optional[str]):
        """Create new session"""
        criteria = {}

        if criteria_file:
            if not os.path.exists(criteria_file):
                print(f"Error: Criteria file not found: {criteria_file}")
                sys.exit(1)

            with open(criteria_file, 'r') as f:
                criteria = json.load(f)

        session_id = create_session(criteria)
        print(f"Created session {session_id}")

    def _archive_session(self, session_id: int):
        """Archive a session"""
        update_session_status(session_id, 'archived')
        print(f"Session {session_id} archived")

    def _db_stats(self, session_id: Optional[int]):
        """Show database statistics"""
        if session_id:
            stats = get_session_stats(session_id)
            print(f"\nSession {session_id} Statistics:")
        else:
            stats = get_database_stats()
            print("\nDatabase Statistics:")

        self._print_stats(stats)

    def _db_export(self, session_id: Optional[int], output_file: Optional[str]):
        """Export database to JSON"""
        cli_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, cli_dir)
        from progress import ProgressTracker

        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'portin_export_{timestamp}.json'

        with ProgressTracker("Database Export", "Collecting data...") as progress:
            data = {
                'exported_at': datetime.now().isoformat(),
                'sessions': []
            }

            if session_id:
                sessions = [get_session(session_id)]
            else:
                sessions = [get_session(s['id']) for s in get_all_sessions()]

            progress.update(task=f"Exporting {len(sessions)} sessions...")

            for i, session in enumerate(sessions, 1):
                if session:
                    progress.update(task=f"Exporting session {i}/{len(sessions)}...")
                    companies = get_companies_by_session(session['id'])
                    session['companies'] = companies
                    data['sessions'].append(session)

            progress.update(task="Writing to file...")
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)

        print(f"Exported to: {output_file}")

    def _db_backup(self, output_file: Optional[str]):
        """Backup database file"""
        import shutil
        cli_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, cli_dir)
        from progress import ProgressTracker

        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'portin_backup_{timestamp}.db'

        with ProgressTracker("Database Backup", "Copying database file...") as progress:
            shutil.copy2(DB_PATH, output_file)

        print(f"Database backed up to: {output_file}")
        print(f"Size: {self._get_file_size(output_file)}")

    def _db_clean(self):
        """Clean up database"""
        print("Database cleanup options:")
        print("1. Remove failed companies")
        print("2. Remove duplicate companies")
        print("3. Archive old sessions")
        print("4. Vacuum database")

        choice = input("\nSelect option (1-4, or 'cancel'): ").strip()

        if choice == '1':
            from data.db import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM companies WHERE status = 'failed'")
                deleted = cursor.rowcount
            print(f"Removed {deleted} failed companies")

        elif choice == '4':
            from data.db import get_db_connection
            with get_db_connection() as conn:
                conn.execute("VACUUM")
            print("Database vacuumed")

        else:
            print("Cancelled")

    def _db_companies(self, session_id: Optional[int], status: Optional[str]):
        """List companies in database"""
        if session_id:
            companies = get_companies_by_session(session_id, status)
        else:
            companies = get_all_known_companies()

        print(f"\nTotal Companies: {len(companies)}")

        if companies:
            print("-" * 80)
            print(f"{'Name':<40} {'Domain':<30} {'Score':<10}")
            print("-" * 80)

            for c in companies[:50]:
                name = c.get('name', 'N/A')[:39]
                domain = c.get('domain', 'N/A')[:29]
                score = c.get('best_score') or c.get('score') or 0
                print(f"{name:<40} {domain:<30} {score:<10.1f}")

            if len(companies) > 50:
                print(f"\n... and {len(companies) - 50} more")

    def _list_companies(self, session_id: Optional[int], status: Optional[str], limit: int):
        """List companies"""
        if not session_id:
            print("Error: --session required")
            sys.exit(1)

        companies = get_companies_by_session(session_id, status)

        print(f"\nSession {session_id} - {len(companies)} companies")

        if status:
            print(f"Status filter: {status}")

        print("-" * 100)
        print(f"{'ID':<6} {'Name':<35} {'Domain':<25} {'Status':<12} {'Score':<10}")
        print("-" * 100)

        for c in companies[:limit]:
            cid = c.get('id', 'N/A')
            name = c.get('name', 'N/A')[:34]
            domain = c.get('domain', 'N/A')[:24]
            cstatus = c.get('status', 'N/A')
            score = c.get('score', 0) or 0

            print(f"{cid:<6} {name:<35} {domain:<25} {cstatus:<12} {score:<10.1f}")

        if len(companies) > limit:
            print(f"\n... and {len(companies) - limit} more (use --limit to see more)")

    def _export_companies(self, session_id: Optional[int], status: Optional[str], output_file: Optional[str]):
        """Export companies to JSON"""
        cli_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, cli_dir)
        from progress import ProgressTracker

        if not session_id:
            print("Error: --session required")
            sys.exit(1)

        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'companies_session_{session_id}_{timestamp}.json'

        with ProgressTracker("Company Export", f"Loading companies from session {session_id}...") as progress:
            companies = get_companies_by_session(session_id, status)

            progress.update(task=f"Exporting {len(companies)} companies...")

            data = {
                'session_id': session_id,
                'exported_at': datetime.now().isoformat(),
                'count': len(companies),
                'companies': companies
            }

            progress.update(task="Writing to file...")
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)

        print(f"Exported {len(companies)} companies to: {output_file}")

    def _print_stats(self, stats: dict):
        """Print statistics in formatted table"""
        print("-" * 40)
        for key, value in stats.items():
            label = key.replace('_', ' ').title()
            print(f"  {label:<25} {value:>10}")
        print("-" * 40)

    def _get_file_size(self, filepath: str) -> str:
        """Get human-readable file size"""
        if not os.path.exists(filepath):
            return "0 B"

        size = os.path.getsize(filepath)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def _check_api_keys(self):
        """Check API key status"""
        from dotenv import load_dotenv
        load_dotenv()

        keys = {
            'GEMINI_API_KEY': 'Gemini',
            'SERPER_KEY': 'Serper',
            'FIRECRAWL_KEY': 'Firecrawl',
            'COMPANIES_HOUSE_API_KEY': 'Companies House',
            'OPENCORPORATES_API_KEY': 'OpenCorporates'
        }

        for key, name in keys.items():
            status = "configured" if os.getenv(key) else "not set"
            print(f"  {name:<20} {status}")


def main():
    cli = PortinCLI()
    cli.run()


if __name__ == '__main__':
    main()
