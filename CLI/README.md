# Portin CLI

Clean command-line interface for Portin M&A Discovery System.

Run from project root directory.

## Quick Start

```bash
python3 CLI/portin.py guide
python3 CLI/portin.py status
```

## Usage

```bash
python3 CLI/portin.py <command> [options]
```

## Main Commands

- `status` - System overview
- `guide` - Full usage guide
- `run <phase>` - Run pipeline (intake, discovery, enrichment, pipeline, dashboard)
- `sessions <action>` - Manage sessions (list, show, create, archive)
- `companies <action>` - View/export companies (list, export)
- `db <action>` - Database operations (stats, export, backup, clean)

## Examples

```bash
python3 CLI/portin.py run intake
python3 CLI/portin.py sessions list
python3 CLI/portin.py companies list --session 3 --status enriched
python3 CLI/portin.py db backup
```

## Help

Every command has built-in help:

```bash
python3 CLI/portin.py --help
python3 CLI/portin.py guide
python3 CLI/portin.py sessions --help
```

## Features

- Real-time progress tracking with elapsed time
- Keyboard interrupt support (Ctrl+C)
- Token usage tracking for API calls
- Database management and backup
- Session-based workflow organization
- Company filtering and export
