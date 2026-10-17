"""Local backup utility; safe SQLite snapshots include a live database."""
import argparse, sqlite3
from pathlib import Path
from datetime import datetime, timezone

def backup(source=None):
    root=Path(__file__).resolve().parent
    source=Path(source) if source else root/'instance'/'collectify.db'
    if not source.exists():
        raise SystemExit('No local database yet. Start the app first.')
    folder=root/'instance'/'backups';folder.mkdir(parents=True,exist_ok=True)
    target=folder/('collectify-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.db')
    with sqlite3.connect(source) as original, sqlite3.connect(target) as copy:
        original.backup(copy)
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['backup'])
    parser.parse_args();print('Backup saved:',backup())
