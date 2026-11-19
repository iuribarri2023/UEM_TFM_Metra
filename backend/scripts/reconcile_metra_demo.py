"""Non-destructive, three-way reconciliation of the active METRA-DEMO corpus with PostgreSQL."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from secrets import token_urlsafe

from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from app.models import User
from argon2 import PasswordHasher
ph=PasswordHasher()
from app.source_reconciliation import reconcile
from app.catalogue import install_templates
from app.inventory import inventory
from scripts.catalogue_data import validate
from scripts.import_metra_demo import IMPORT_AUTHOR


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Apply only safe operations; never overwrite publication')
    parser.add_argument('--dry-run',action='store_true',help='Explicitly request read-only analysis')
    parser.add_argument('--report',nargs='?',const='-',default=None,help='Write JSON report to path or stdout (-)')
    args=parser.parse_args()
    if args.apply and args.dry_run:parser.error('--apply and --dry-run are incompatible')
    if not os.getenv('DATABASE_URL'):
        parser.error('DATABASE_URL is required')
    validate()
    root=BACKEND/'data/metra-demo'
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,pool_pre_ping=True)
    with Session(engine) as db:
        db.execute(text('SELECT pg_advisory_xact_lock(287197612)'))
        if args.apply:
            # Provision a disabled technical identity only; never create an admin account.
            author=db.scalar(select(User).where(User.email==IMPORT_AUTHOR))
            if author is None:
                db.add(User(email=IMPORT_AUTHOR,role='ADMIN',active=False,
                            password_hash=ph.hash(token_urlsafe(42))))
                db.flush()
            elif author.active:
                raise RuntimeError('The technical import account must remain disabled')
        report=reconcile(db,root,Path(os.getenv('ASSET_DIR','/data/assets')).resolve(),apply=args.apply)
        if args.apply:
            report['templates_created']=install_templates(db)
            db.commit()
        else:
            db.rollback()
    counts=report['counts']
    print(f"METRA-DEMO {report['mode']}: new={counts['new']}; synced={counts['synced']}; "
          f"updated={counts['updated']}; proposals={counts['proposed']}; "
          f"conflicts={counts['conflicts']}; unbaselined={counts['unbaselined']}; "
          f"orphans={counts['orphaned']}")
    if args.report is not None:
        payload=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
        if args.report=='-':print(payload)
        else:
            out=Path(args.report).resolve()
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(payload,encoding='utf-8')
    if counts['conflicts'] or counts['unbaselined']:
        print('Unresolved origin differences are preserved and require review.',file=sys.stderr)


if __name__=='__main__':main()
