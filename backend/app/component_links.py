"""Explicit, revision-scoped associations from IFC components to BC3 and EPD."""
from flask import g, request
from pydantic import BaseModel, Field
from sqlalchemy import column, func, select, true
from sqlalchemy.dialects.postgresql import JSONB

from .api_support import api, audit, data, dto, err, obj, page_query, pk, revision_owned
from .documents import extraction_query
from .models import Asset, CommercialSolution, ComponentDocumentLink, Extraction, Revision, RevisionAsset
from .security import get_user, role


class LinkInput(BaseModel):
    ifc_asset_id: str
    ifc_global_id: str = Field(pattern=r'^[0-9A-Za-z_$]{22}$')
    target_asset_id: str
    concept_code: str = Field(default='', max_length=120)
    material: str = Field(default='', max_length=255)
    unit: str = Field(default='', max_length=100)
    evidence: str = Field(min_length=10, max_length=2000)


def member(revision, asset_id):
    link = g.db.get(RevisionAsset, (revision.id, pk(asset_id)))
    if not link:
        err('El documento no pertenece a esta revisión', 'NOT_FOUND', 404)
    return obj(Asset, asset_id), link


def entry(asset, array, key, value):
    entries = func.jsonb_array_elements(Extraction.normalized[array]).table_valued(column('value', JSONB), joins_implicitly=True)
    rows = entries.c.value
    return g.db.scalar(select(rows).select_from(Extraction).join(entries, true()).where(
        Extraction.id == extraction_query(asset), Extraction.is_valid == True,
        rows[key].astext == value).limit(1))


def serialize_link(link, asset, private=False):
    result = {
        'id': str(link.id), 'kind': asset.file_type, 'document_id': str(asset.id),
        'document_name': asset.original_name, 'concept_code': link.concept_code or None,
        'material': link.material or None, 'unit': link.unit or None, 'method': 'MANUAL',
    }
    if private:
        result.update(evidence=link.evidence, author_id=str(link.author_id), created_at=link.created_at.isoformat())
    return result


@api.get('/revisions/<id>/component-links')
def component_links(id):
    revision = obj(Revision, id)
    product = obj(CommercialSolution, revision.product_id)
    user = get_user(False)
    private = bool(user and (user.role == 'ADMIN' or user.manufacturer_id == product.manufacturer_id))
    if not private and (product.availability != 'ACTIVE' or product.published_revision_id != revision.id
                        or revision.status != 'APPROVED'):
        err('Revisión no disponible', 'NOT_FOUND', 404)
    source, policy = member(revision, request.args.get('ifc_asset_id'))
    if source.file_type != 'IFC' or source.processing_status != 'VALID' or not (private or policy.public_view_allowed):
        err('IFC no disponible', 'NOT_FOUND', 404)
    guid = request.args.get('global_id', '')
    if len(guid) != 22:
        err('GlobalId IFC inválido', 'VALIDATION', 422)

    target_policy = RevisionAsset
    query = (select(ComponentDocumentLink)
             .join(target_policy, (target_policy.revision_id == ComponentDocumentLink.revision_id)
                   & (target_policy.asset_id == ComponentDocumentLink.target_asset_id))
             .join(Asset, Asset.id == target_policy.asset_id)
             .where(ComponentDocumentLink.revision_id == revision.id,
                    ComponentDocumentLink.ifc_asset_id == source.id,
                    ComponentDocumentLink.ifc_global_id == guid,
                    Asset.processing_status == 'VALID'))
    if not private:
        query = query.where(target_policy.public_download_allowed == True)
    rows, meta = page_query(query.order_by(ComponentDocumentLink.created_at, ComponentDocumentLink.id))
    return data([serialize_link(row, g.db.get(Asset, row.target_asset_id), private) for row in rows], meta)


@api.post('/manufacturer/revisions/<id>/component-links')
@role('MANUFACTURER')
def create_component_link(id):
    revision, _ = revision_owned(id, True)
    if revision.status != 'DRAFT':
        err('Los vínculos se editan en borradores', 'IMMUTABLE', 409)
    body = dto(LinkInput)
    source, _ = member(revision, body.ifc_asset_id)
    target, _ = member(revision, body.target_asset_id)
    if source.file_type != 'IFC' or source.processing_status != 'VALID':
        err('Selecciona un IFC válido', 'VALIDATION', 422)
    if target.file_type not in ('BC3', 'EPD') or target.processing_status != 'VALID':
        err('Selecciona un BC3 o EPD válido', 'VALIDATION', 422)
    component = entry(source, 'elements', 'global_id', body.ifc_global_id)
    if component is None:
        err('El componente no existe en el IFC seleccionado', 'VALIDATION', 422)
    material = body.material.strip()
    if material and material not in (component.get('materials') or []):
        err('El material no está declarado en el componente', 'VALIDATION', 422)
    code = body.concept_code.strip()
    if target.file_type == 'BC3' and (not code or entry(target, 'concepts', 'code', code) is None):
        err('El concepto no existe en el BC3 seleccionado', 'VALIDATION', 422)
    if target.file_type == 'EPD' and code:
        err('El código de concepto solo se admite para BC3', 'VALIDATION', 422)
    evidence = body.evidence.strip()
    if len(evidence) < 10:
        err('Registra la evidencia del vínculo', 'VALIDATION', 422)
    link = ComponentDocumentLink(revision_id=revision.id, ifc_asset_id=source.id,
                                 ifc_global_id=body.ifc_global_id, target_asset_id=target.id,
                                 concept_code=code, material=material, unit=body.unit.strip(),
                                 evidence=evidence, author_id=get_user().id)
    g.db.add(link)
    g.db.flush()
    audit('CREATE_COMPONENT_LINK', 'revision', revision.id, {'link_id': str(link.id)})
    return data(serialize_link(link, target, True), status=201)


@api.delete('/manufacturer/revisions/<id>/component-links/<link_id>')
@role('MANUFACTURER')
def remove_component_link(id, link_id):
    revision, _ = revision_owned(id, True)
    if revision.status != 'DRAFT':
        err('Los vínculos se editan en borradores', 'IMMUTABLE', 409)
    link = obj(ComponentDocumentLink, link_id)
    if link.revision_id != revision.id:
        err('Vínculo no disponible', 'NOT_FOUND', 404)
    g.db.delete(link)
    audit('DELETE_COMPONENT_LINK', 'revision', revision.id, {'link_id': str(link.id)})
    return data({'deleted': True})
