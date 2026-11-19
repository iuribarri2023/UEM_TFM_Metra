"""Shared request, response and authorization helpers for REST v1."""

from collections import defaultdict

import os, re, secrets, hashlib

from datetime import timedelta

from pathlib import Path

from uuid import UUID,uuid4

from flask import Response, Blueprint, current_app, g, jsonify, request, make_response, send_file

from pydantic import ValidationError

from sqlalchemy import select,func,or_,text

from sqlalchemy.exc import IntegrityError

from werkzeug.utils import secure_filename

from .models import (System,Subsystem,Archetype,GenericSolution,GenericSlot,DataTemplate,
 Manufacturer,User,Invitation,RefreshSession,CommercialSolution,Revision,RevisionGeneric,
 Asset,RevisionAsset,GenericAsset,Extraction,ReviewDecision,Notification,AuditLog,
 RevisionOrigin,PriceBook,PriceBookVersion,CostImport,DocumentJob,ComponentDocumentLink,now)

from .security import (ph,hash_token,access_token,grant_refresh,check_csrf,current_refresh,get_user,role,fail)

from .validation import (RegisterDTO,InviteAcceptDTO,LoginDTO,ProductDTO,RevisionDTO,
 CatalogueDTO,TemplateDTO,check_template,discrepancies)

from .parsers import ParseFailure,export_bc3

from .ifc_thumbnails import thumbnail_path

from .comparison import parse_pair, warnings_for

from .catalogue import project, current_template

from .data_quality import quality_report

api=Blueprint('api_v1',__name__,url_prefix='/api/v1')

class ApiError(Exception):
    def __init__(self,code,message,status=400,details=None):
        self.code,self.message,self.status,self.details=code,message,status,details or []
        super().__init__(message)

def data(value,meta=None,status=200):return jsonify({'data':value,'meta':meta or {}}),status

def err(message,code='INVALID',status=400):raise ApiError(code,message,status)

def pk(value):
    try:return UUID(str(value))
    except (ValueError,TypeError):err('UUID inválido','VALIDATION',422)

def obj(model,id,locking=False):
    q=select(model).where(model.id==pk(id))
    if locking:q=q.with_for_update()
    val=g.db.scalar(q)
    if not val:err('Recurso no encontrado','NOT_FOUND',404)
    return val

def dto(cls):
    if not request.is_json:err('Se requiere JSON','BAD_JSON',415)
    try:return cls.model_validate(request.get_json())
    except ValidationError as e:raise ApiError('VALIDATION','Datos inválidos',422,e.errors(include_url=False))

def fields(x,names):
    return {k:(str(getattr(x,k)) if isinstance(getattr(x,k),UUID) else getattr(x,k)) for k in names}

def owner(product,lock=False):
    u=get_user()
    if u.role!='ADMIN' and u.manufacturer_id!=product.manufacturer_id:err('Recurso no encontrado','NOT_FOUND',404)
    return u

def revision_owned(id,lock=False):
    r=obj(Revision,id,lock)
    p=obj(CommercialSolution,r.product_id,lock)
    owner(p)
    return r,p

def notify(users,event,message):
    for user in users:g.db.add(Notification(user_id=user.id,event=event,message=message))

def audit(action,entity,item,detail=None):
    u=get_user(False)
    g.db.add(AuditLog(actor_id=u.id if u else None,action=action,entity=entity,entity_id=str(item),detail=detail or {}))

def page_query(query):
    try:page=int(request.args.get('page',1));size=int(request.args.get('page_size',20))
    except ValueError:err('Paginación inválida','VALIDATION',422)
    if not 1<=page<=10000 or not 1<=size<=100:err('Paginación fuera de límites','VALIDATION',422)
    total=g.db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return list(g.db.scalars(query.limit(size).offset((page-1)*size))),{'page':page,'page_size':size,'total':total}

MODELS={'systems':System,'subsystems':Subsystem,'archetypes':Archetype,'generic-solutions':GenericSolution,'slots':GenericSlot}
