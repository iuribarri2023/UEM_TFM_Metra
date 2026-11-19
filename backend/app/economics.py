"""Economic reference catalogs and revision-scoped estimates."""
from decimal import Decimal
from io import BytesIO
from math import isfinite

from flask import g, request, send_file
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select

from .api_support import api, asset_access, audit, data, dto, err, obj, page_query, pk
from .models import (Budget, BudgetItem, CommercialSolution, Extraction,
                     PriceBook, PriceBookVersion, PriceConcept, Revision)
from .parsers import export_bc3
from .security import get_user, role


class Title(BaseModel):
    name: str = Field(min_length=1, max_length=180)

    @field_validator('name')
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value or any(c in value for c in ('|','~','\r','\n','\x00')):
            raise ValueError('Nombre inválido')
        return value


class ItemInput(BaseModel):
    code: str = Field(pattern=r'^[A-Za-z0-9._-]{1,90}$')
    description: str = Field(min_length=1,max_length=400)
    unit: str = Field(min_length=1,max_length=24)
    quantity: Decimal = Field(ge=0,max_digits=20,decimal_places=6)
    unit_price: Decimal = Field(max_digits=20,decimal_places=6)

    @field_validator('description','unit')
    @classmethod
    def safe_bc3(cls,value):
        return Title.clean(value)


class ConceptInput(BaseModel):
    unit: str = Field(max_length=24)
    description: str = Field(min_length=1,max_length=400)
    unit_price: float

    @field_validator('unit_price')
    @classmethod
    def finite(cls,value):
        if not isfinite(value):raise ValueError('Precio no finito')
        return value

    @field_validator('unit','description')
    @classmethod
    def safe_bc3(cls,value):
        if any(c in value for c in ('|','~','\r','\n','\x00')):
            raise ValueError('Campo BC3 inválido')
        return value


def book(id,lock=False):
    row=obj(PriceBook,id,lock)
    if row.archived:err('Base de costes no disponible','NOT_FOUND',404)
    return row


def version(book_id,required=True):
    query=select(PriceBookVersion).where(PriceBookVersion.book_id==book_id)
    requested=request.args.get('version_id')
    if requested:query=query.where(PriceBookVersion.id==pk(requested))
    row=g.db.scalar(query.order_by(PriceBookVersion.created_at.desc(),PriceBookVersion.id).limit(1))
    if required and not row:err('Versión no encontrada','NOT_FOUND',404)
    return row


def book_data(row):
    v=version(row.id,False)
    return {'id':str(row.id),'name':row.name,'version_id':str(v.id) if v else None,
            'sha256':v.sha256 if v else None,
            'created_at':(v.created_at if v else row.created_at).isoformat()}


@api.get('/cost-databases')
@role('ADMIN')
def cost_databases():
    rows,meta=page_query(select(PriceBook).where(PriceBook.archived==False).order_by(PriceBook.name))
    return data([book_data(row) for row in rows],meta)


@api.post('/cost-databases')
@role('ADMIN')
def create_cost_database():
    row=PriceBook(name=dto(Title).name)
    g.db.add(row);g.db.flush()
    return data(book_data(row),status=201)


@api.get('/cost-databases/<id>')
@role('ADMIN')
def cost_database(id):
    return data(book_data(book(id)))


@api.patch('/cost-databases/<id>')
@role('ADMIN')
def update_cost_database(id):
    row=book(id,True)
    row.name=dto(Title).name
    audit('RENAME_COST_DATABASE','cost-database',row.id)
    return data(book_data(row))


@api.delete('/cost-databases/<id>')
@role('ADMIN')
def archive_cost_database(id):
    row=book(id,True);row.archived=True
    audit('ARCHIVE_COST_DATABASE','cost-database',row.id)
    return data({'archived':True})


def concept_row(id,concept_id):
    v=version(book(id).id)
    row=g.db.get(PriceConcept,(v.id,concept_id))
    if not row:err('Concepto no encontrado','NOT_FOUND',404)
    return row


def concept_data(row):
    return dict(code=row.code,unit=row.unit,description=row.description,
                **{k:v for k,v in row.values.items() if k not in {'children','text'}})


@api.get('/cost-databases/<id>/concepts')
@role('ADMIN')
def cost_concepts(id):
    v=version(book(id).id)
    q=select(PriceConcept).where(PriceConcept.version_id==v.id)
    term=request.args.get('q','').strip()[:150]
    if term:q=q.where(or_(PriceConcept.code.icontains(term,autoescape=True),
                          PriceConcept.description.icontains(term,autoescape=True)))
    if request.args.get('unit'):q=q.where(PriceConcept.unit==request.args['unit'])
    rows,meta=page_query(q.order_by(PriceConcept.code))
    return data([concept_data(row) for row in rows],meta)


@api.get('/cost-databases/<id>/concepts/<path:concept_id>')
@role('ADMIN')
def cost_concept(id,concept_id):
    row=concept_row(id,concept_id)
    return data(dict(**concept_data(row),text=row.values.get('text')))


@api.patch('/cost-databases/<id>/concepts/<path:concept_id>')
@role('ADMIN')
def edit_cost_concept(id,concept_id):
    book(id,True)
    row=concept_row(id,concept_id)
    value=dto(ConceptInput)
    prices=row.values.get('prices') or []
    row.unit,row.description=value.unit,value.description
    row.values={**row.values,'prices':[value.unit_price,*prices[1:]],'unit_price':value.unit_price,
                'edited':True}
    audit('UPDATE_COST_CONCEPT','cost-database',id,{'code':row.code})
    return data(concept_data(row))


@api.get('/cost-databases/<id>/concepts/<path:concept_id>/decomposition')
@role('ADMIN')
def cost_decomposition(id,concept_id):
    return data(concept_row(id,concept_id).values.get('children',[]))


def extraction(v):
    return g.db.scalar(select(Extraction.normalized).where(Extraction.asset_id==v.asset_id,
        Extraction.is_valid==True).order_by(Extraction.created_at.desc()).limit(1))


@api.get('/cost-databases/<id>/hierarchy')
@role('ADMIN')
def cost_hierarchy(id):
    v=version(book(id).id)
    code=request.args.get('parent')
    if code is None:
        code=g.db.scalar(select(PriceConcept.code).where(PriceConcept.version_id==v.id,
              PriceConcept.code.endswith('##')).order_by(PriceConcept.code).limit(1))
    if not code:return data({'code':None,'children':[]})
    row=concept_row(id,code)
    return data({'code':code,'children':row.values.get('children',[])})


def bc3_response(blob,name):
    return send_file(BytesIO(blob),mimetype='application/octet-stream',download_name=name,as_attachment=True)


@api.get('/cost-databases/<id>/export/bc3')
@role('ADMIN')
def export_cost_database(id):
    v=version(book(id).id)
    normalized=extraction(v)
    if not normalized or not normalized.get('records'):err('No hay extracción exportable','VALIDATION',422)
    rows=g.db.scalars(select(PriceConcept).where(PriceConcept.version_id==v.id,
                                  PriceConcept.values['edited'].as_boolean()==True))
    edited={row.code:row for row in rows}
    for tag,fields in normalized['records']:
        if tag!='C' or not fields:continue
        row=edited.get(fields[0].split(chr(92))[0].strip())
        if not row:continue
        while len(fields)<4:fields.append('')
        fields[1:3]=[row.unit,row.description]
        previous=fields[3].split(chr(92))
        fields[3]=chr(92).join([str(row.values['unit_price']),*previous[1:]])
    try:return bc3_response(export_bc3(normalized),'base-costes.bc3')
    except UnicodeEncodeError:err('La edición contiene caracteres ajenos a la codificación original','VALIDATION',422)


@api.get('/cost-databases/<id>/source-file')
@role('ADMIN')
def cost_source(id):
    return asset_access(version(book(id).id).asset_id,'download')


def budget_record(id,write=False):
    row=obj(Budget,id,write)
    u=get_user(False)
    revision=g.db.get(Revision,row.revision_id) if row.revision_id else None
    owner=bool(u and (u.role=='ADMIN' or u.manufacturer_id and u.manufacturer_id==row.manufacturer_id))
    public=False
    if revision and revision.status=='APPROVED':
        p=g.db.get(CommercialSolution,revision.product_id)
        public=bool(p and p.published_revision_id==revision.id and p.availability=='ACTIVE')
    if row.archived or not (owner or public and not write):err('Presupuesto no encontrado','NOT_FOUND',404)
    if write and revision and revision.status!='DRAFT':err('Presupuesto de revisión inmutable','IMMUTABLE',409)
    if write and revision:
        # Serialize edits with submission, which locks the same revision.
        revision=obj(Revision,revision.id,True)
        g.db.refresh(revision)
        if revision.status!='DRAFT':err('Presupuesto de revisión inmutable','IMMUTABLE',409)
    return row


def budget_data(row):
    return {'id':str(row.id),'name':row.name,'revision_id':str(row.revision_id) if row.revision_id else None}


def create_budget_row(revision=None,manufacturer_id=None):
    u=get_user()
    row=Budget(name=dto(Title).name,manufacturer_id=manufacturer_id or u.manufacturer_id,
               revision_id=revision.id if revision else None)
    g.db.add(row);g.db.flush()
    audit('CREATE_BUDGET','budget',row.id)
    return data(budget_data(row),status=201)


@api.get('/budgets')
def budgets():
    u=get_user()
    q=select(Budget).where(Budget.archived==False)
    if u.role!='ADMIN':q=q.where(Budget.manufacturer_id==u.manufacturer_id)
    rows,meta=page_query(q.order_by(Budget.name,Budget.id))
    return data([budget_data(row) for row in rows],meta)


@api.post('/budgets')
def create_budget():
    return create_budget_row()


@api.get('/budgets/<id>')
def budget(id):
    return data(budget_data(budget_record(id)))


@api.patch('/budgets/<id>')
def update_budget(id):
    row=budget_record(id,True);row.name=dto(Title).name
    audit('UPDATE_BUDGET','budget',row.id)
    return data(budget_data(row))


@api.delete('/budgets/<id>')
def archive_budget(id):
    row=budget_record(id,True);row.archived=True
    audit('ARCHIVE_BUDGET','budget',row.id)
    return data({'archived':True})


def item_data(row):
    return dict(id=str(row.id),code=row.code,description=row.description,unit=row.unit,
                quantity=str(row.quantity),unit_price=str(row.unit_price),
                total=str(row.quantity*row.unit_price))


def item_query(id):
    return select(BudgetItem).where(BudgetItem.budget_id==id)


@api.get('/budgets/<id>/items')
def budget_items(id):
    row=budget_record(id)
    items,meta=page_query(item_query(row.id).order_by(BudgetItem.code))
    return data([item_data(item) for item in items],meta)


@api.post('/budgets/<id>/items')
def create_budget_item(id):
    row=budget_record(id,True)
    item=BudgetItem(budget_id=row.id,**dto(ItemInput).model_dump())
    g.db.add(item);g.db.flush()
    audit('CREATE_BUDGET_ITEM','budget',row.id,{'item_id':str(item.id)})
    return data(item_data(item),status=201)


def budget_item(id,item_id):
    budget=budget_record(id,True)
    item=g.db.scalar(item_query(budget.id).where(BudgetItem.id==pk(item_id)))
    if not item:err('Partida no encontrada','NOT_FOUND',404)
    return item


@api.patch('/budgets/<id>/items/<item_id>')
def update_budget_item(id,item_id):
    item=budget_item(id,item_id)
    for key,value in dto(ItemInput).model_dump().items():setattr(item,key,value)
    audit('UPDATE_BUDGET_ITEM','budget',id,{'item_id':item_id})
    return data(item_data(item))


@api.delete('/budgets/<id>/items/<item_id>')
def delete_budget_item(id,item_id):
    item=budget_item(id,item_id);g.db.delete(item)
    audit('DELETE_BUDGET_ITEM','budget',id,{'item_id':item_id})
    return data({'deleted':True})


@api.get('/budgets/<id>/totals')
def budget_totals(id):
    row=budget_record(id)
    count,total=g.db.execute(select(func.count(),func.sum(BudgetItem.quantity*BudgetItem.unit_price))
                            .where(BudgetItem.budget_id==row.id)).one()
    return data({'items':count,'total':str(total or Decimal(0))})


@api.get('/budgets/<id>/export/bc3')
def budget_export(id):
    row=budget_record(id)
    root='METRA##'
    slash=chr(92)
    items=list(g.db.scalars(item_query(row.id).order_by(BudgetItem.code)))
    records=[['V',['METRA','FIEBDC-3/2020','','','UTF-8','']],
             ['C',[root,'',row.name,str(sum((i.quantity*i.unit_price for i in items),Decimal(0))),'','','']]]
    records.extend(['C',[i.code,i.unit,i.description,str(i.unit_price),'','','']] for i in items)
    if items:records.append(['D',[root,slash.join(part for i in items for part in
                                    (i.code,'1',str(i.quantity)))+slash,'']])
    return bc3_response(export_bc3({'encoding':'utf-8','records':records}),'presupuesto.bc3')


@api.get('/products/<id>/budgets')
def product_budgets(id):
    p=obj(CommercialSolution,id)
    u=get_user(False)
    q=select(Budget).join(Revision).where(Budget.archived==False,Revision.product_id==p.id)
    if not (u and (u.role=='ADMIN' or p.manufacturer_id==u.manufacturer_id)):
        if p.availability!='ACTIVE' or not p.published_revision_id:err('Producto no encontrado','NOT_FOUND',404)
        q=q.where(Revision.id==p.published_revision_id,Revision.status=='APPROVED')
    rows,meta=page_query(q.order_by(Budget.name,Budget.id))
    return data([budget_data(row) for row in rows],meta)


@api.post('/products/<id>/budgets')
def create_product_budget(id):
    u=get_user()
    p=obj(CommercialSolution,id)
    if u.role!='ADMIN' and p.manufacturer_id!=u.manufacturer_id:err('Producto no encontrado','NOT_FOUND',404)
    draft=g.db.scalar(select(Revision).where(Revision.product_id==p.id,Revision.status=='DRAFT').with_for_update())
    if not draft:err('El producto requiere un borrador','CONFLICT',409)
    return create_budget_row(draft,p.manufacturer_id)
