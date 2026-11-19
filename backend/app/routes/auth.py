"""Versioned HTTP endpoints for auth."""
from ..api_support import (
    Invitation,
    InviteAcceptDTO,
    LoginDTO,
    Manufacturer,
    RefreshSession,
    RegisterDTO,
    User,
    access_token,
    api,
    audit,
    check_csrf,
    current_refresh,
    data,
    dto,
    err,
    fields,
    func,
    g,
    get_user,
    grant_refresh,
    hash_token,
    jsonify,
    make_response,
    now,
    obj,
    ph,
    request,
    select,
    uuid4,
)


@api.post('/auth/register')
def register():
    b=dto(RegisterDTO);email=str(b.email).lower()
    if g.db.scalar(select(User.id).where(User.email==email)):err('Correo ya registrado','CONFLICT',409)
    organization=b.manufacturer_name.strip()
    if len(organization)<2:err('Nombre de empresa inválido','VALIDATION',422)
    if g.db.scalar(select(Manufacturer.id).where(func.lower(Manufacturer.name)==organization.lower()).limit(1)):
        err('La empresa ya existe. Solicita una invitación','CONFLICT',409)
    m=Manufacturer(name=organization,code='ORG-'+uuid4().hex[:12].upper());g.db.add(m);g.db.flush()
    u=User(email=email,password_hash=ph.hash(b.password),role='MANUFACTURER',manufacturer_id=m.id)
    g.db.add(u);g.db.flush();audit('REGISTER','manufacturer',m.id)
    resp=make_response(jsonify({'data':{'access_token':access_token(u),'role':u.role,'manufacturer_id':str(m.id)},'meta':{}}),201)
    return grant_refresh(resp,u)



@api.post('/auth/login')
def login():
    b=dto(LoginDTO);u=g.db.scalar(select(User).where(User.email==str(b.email).lower()))
    try:valid=bool(u and u.active and ph.verify(u.password_hash,b.password))
    except Exception:valid=False
    if not valid:err('Credenciales inválidas','UNAUTHORIZED',401)
    resp=make_response(jsonify({'data':{'access_token':access_token(u),'role':u.role},'meta':{}}))
    return grant_refresh(resp,u)



@api.post('/auth/refresh')
def refresh():
    check_csrf();s=current_refresh();s.revoked_at=now()
    u=obj(User,s.user_id)
    if not u.active:err('Usuario desactivado','UNAUTHORIZED',401)
    return grant_refresh(make_response(jsonify({'data':{'access_token':access_token(u)},'meta':{}})),u)



@api.post('/auth/logout')
def logout():
    check_csrf()
    if request.cookies.get('refresh'):
        s=g.db.scalar(select(RefreshSession).where(RefreshSession.token_hash==hash_token(request.cookies['refresh'])))
        if s:s.revoked_at=now()
    resp=make_response(jsonify({'data':{'logged_out':True},'meta':{}}))
    resp.delete_cookie('refresh',path='/api/v1/auth');resp.delete_cookie('csrf',path='/')
    return resp



@api.get('/auth/me')
def me():
    u=get_user();return data(fields(u,['id','email','role','manufacturer_id']))



@api.post('/auth/accept-invitation')
def accept_invitation():
    b=dto(InviteAcceptDTO);email=str(b.email).lower()
    inv=g.db.scalar(select(Invitation).where(Invitation.token_hash==hash_token(b.token)).with_for_update())
    if not inv or inv.used_at or inv.expires_at<now() or inv.email!=email:err('Invitación inválida/caducada','INVITATION',422)
    if g.db.scalar(select(User).where(User.email==email)):err('Correo registrado','CONFLICT',409)
    u=User(email=email,password_hash=ph.hash(b.password),role='MANUFACTURER',manufacturer_id=inv.manufacturer_id)
    inv.used_at=now();g.db.add(u);g.db.flush();audit('JOIN','manufacturer',inv.manufacturer_id)
    return grant_refresh(make_response(jsonify({'data':{'access_token':access_token(u)},'meta':{}}),201),u)

