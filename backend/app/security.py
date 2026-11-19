"""Access tokens in memory, rotating hashed refresh cookies, explicit CSRF double submit."""
import hashlib, os, secrets
from datetime import timedelta
from functools import wraps
from uuid import UUID
from flask import current_app, g, request
from argon2 import PasswordHasher
from jwt import encode, decode, InvalidTokenError
from sqlalchemy import select
from .models import User, RefreshSession, now

ph=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
def hash_token(value): return hashlib.sha256(value.encode()).hexdigest()

def fail(code,message,status=400):
    from .api import ApiError
    raise ApiError(code,message,status)

def get_user(required=True):
    if hasattr(g,'_user'): return g._user
    head=request.headers.get('Authorization','')
    if not head.startswith('Bearer '):
        if required: fail('UNAUTHORIZED','Se requiere autenticación',401)
        return None
    try:
        claims=decode(head[7:],current_app.config['JWT_SECRET'],algorithms=['HS256'],options={'require':['sub','exp','iat']})
        if claims.get('typ')!='access': raise InvalidTokenError()
        u=g.db.get(User,UUID(claims['sub']))
        if not u or not u.active: raise InvalidTokenError()
    except (InvalidTokenError,ValueError): fail('UNAUTHORIZED','Token inválido o caducado',401)
    g._user=u
    return u

def role(which):
    def decorate(fn):
        @wraps(fn)
        def wrapper(*a,**k):
            if get_user().role!=which: fail('FORBIDDEN','Permiso insuficiente',403)
            return fn(*a,**k)
        return wrapper
    return decorate

def access_token(u):
    n=now()
    return encode({'sub':str(u.id),'typ':'access','iat':n,'exp':n+timedelta(minutes=15)},current_app.config['JWT_SECRET'],algorithm='HS256')

def grant_refresh(response,u):
    raw=secrets.token_urlsafe(48)
    session=RefreshSession(user_id=u.id,token_hash=hash_token(raw),expires_at=now()+timedelta(days=14))
    g.db.add(session);g.db.flush()
    secure=current_app.config['COOKIE_SECURE']
    response.set_cookie('refresh',raw,httponly=True,secure=secure,samesite='Lax',path='/api/v1/auth',max_age=1209600)
    response.set_cookie('csrf',secrets.token_urlsafe(32),httponly=False,secure=secure,samesite='Lax',path='/',max_age=1209600)
    return response

def check_csrf():
    if not request.cookies.get('csrf') or not secrets.compare_digest(request.cookies['csrf'],request.headers.get('X-CSRF-Token','')):
        fail('CSRF','CSRF token requerido',403)

def current_refresh():
    raw=request.cookies.get('refresh')
    if not raw: fail('UNAUTHORIZED','Sesión caducada',401)
    session=g.db.scalar(select(RefreshSession).where(RefreshSession.token_hash==hash_token(raw)).with_for_update())
    if not session or session.revoked_at or session.expires_at<now(): fail('UNAUTHORIZED','Sesión caducada',401)
    return session
