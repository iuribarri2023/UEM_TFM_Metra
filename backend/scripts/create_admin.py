# CLI imports the backend package independently of the invocation CWD.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(_Path(__file__).resolve().parents[1]))
import os,getpass,sys
from email_validator import validate_email,EmailNotValidError
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.models import User
from app.security import ph

def main():
    email=os.environ.get('ADMIN_EMAIL') or input('Correo admin: ')
    try: email=validate_email(email,check_deliverability=False).normalized
    except EmailNotValidError as exc: raise SystemExit(str(exc))
    password=os.environ.get('ADMIN_PASSWORD') or getpass.getpass('Contraseña (>=12 caracteres): ')
    if len(password)<12:raise SystemExit('Contraseña demasiado corta')
    with Session(create_engine(os.environ['DATABASE_URL'])) as s:
        if s.scalar(select(User).where(User.email==email.lower())):raise SystemExit('Usuario ya existe')
        s.add(User(email=email.lower(),role='ADMIN',password_hash=ph.hash(password)));s.commit()
    print('Administrador creado')
if __name__=='__main__':main()
