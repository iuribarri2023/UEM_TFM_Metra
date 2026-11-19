"""Backfill/repair the persistent thumbnail queue; the worker also runs it automatically."""
import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.thumbnail_jobs import enqueue_missing, process_thumbnail, repair_missing


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--repair',action='store_true',help='Reprocesar miniaturas desaparecidas')
    parser.add_argument('--retry-failed',action='store_true',help='Reintentar fallos terminales expresamente')
    parser.add_argument('--process',action='store_true',help='Procesar los jobs de este lote en el proceso actual')
    args=parser.parse_args()
    if not 1<=args.limit<=10000:parser.error('--limit debe estar entre 1 y 10000')
    root=Path(os.environ['ASSET_DIR']).resolve()
    engine=create_engine(os.environ['DATABASE_URL'],pool_pre_ping=True,hide_parameters=True)
    queued=enqueue_missing(engine,limit=args.limit)
    repaired=repair_missing(engine,root,limit=args.limit,retry_failed=args.retry_failed) if (args.repair or args.retry_failed) else 0
    processed=0
    if args.process:
        for _ in range(args.limit):
            if not process_thumbnail(engine,root):break
            processed+=1
    print(f'Encolados: {queued}; recuperados: {repaired}; procesados: {processed}. Resto: worker.')


if __name__=='__main__':main()
