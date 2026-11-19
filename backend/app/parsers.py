"""Conservative parsers; semantic/technical validity is not third-party certification."""
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from lxml import etree

class ParseFailure(ValueError): pass

IFC_PRODUCT_INDEX_LIMIT = 10_000

def bc3_bytes(blob):
    """Read a single BC3 member without extracting anything to disk."""
    if not blob.startswith(b'PK'):
        return blob
    from io import BytesIO
    from pathlib import PurePosixPath
    from zipfile import ZipFile, BadZipFile
    try:
        with ZipFile(BytesIO(blob)) as archive:
            members = archive.infolist()
            if len(members) != 1:
                raise ParseFailure('El ZIP debe contener un único BC3')
            member = members[0]
            path = PurePosixPath(member.filename.replace(chr(92), '/'))
            if (path.is_absolute() or len(path.parts) != 1 or ':' in path.name
                    or path.suffix.lower() != '.bc3' or member.flag_bits & 1
                    or member.file_size > 50 * 1024 * 1024
                    or member.file_size > 200 * max(1, member.compress_size)):
                raise ParseFailure('Entrada BC3 insegura o demasiado grande')
            with archive.open(member) as stream:
                value = stream.read(50 * 1024 * 1024 + 1)
            if len(value) > 50 * 1024 * 1024:
                raise ParseFailure('BC3 descomprimido demasiado grande')
            return value
    except (BadZipFile, RuntimeError, NotImplementedError, OSError) as exc:
        raise ParseFailure('ZIP BC3 ilegible') from exc


def parse_bc3(blob: bytes):
    from math import isfinite
    raw = bc3_bytes(blob)
    header = raw.splitlines()[0].upper().split(b'|') if raw.strip() else []
    declared = header[5] if len(header) > 5 and header[0] == b'~V' else b''
    encoding = {b'ANSI': 'cp1252', b'850': 'cp850', b'437': 'cp437',
                b'UTF-8': 'utf-8'}.get(declared, 'utf-8')
    if raw.startswith(b'\xef\xbb\xbf'):
        encoding = 'utf-8-sig'
    try:
        txt = raw.decode(encoding)
    except UnicodeError:
        if declared:
            raise ParseFailure('El BC3 no coincide con la codificación declarada')
        encoding = 'latin-1'
        txt = raw.decode(encoding)
    slash = chr(92)
    concepts, decompositions, texts, records = {}, {}, {}, []
    version = None
    warnings = []
    def number(value):
        try:
            result = float(value.strip().replace(',', '.'))
            return result if isfinite(result) else None
        except ValueError:
            return None
    for match in re.finditer(r'~([A-Z])\|(.*?)(?=~[A-Z]\||\Z)', txt, re.S):
        tag, record = match.groups()
        items = record.rstrip('\r\n').split('|')
        records.append([tag, items])
        if tag == 'V' and len(items) > 1:
            version = items[1].split(slash)[0]
        if tag == 'C' and len(items) >= 3:
            code = items[0].split(slash)[0].strip()
            if not code:
                raise ParseFailure('Concepto sin código')
            prices = items[3].split(slash) if len(items) > 3 and items[3] else []
            concepts[code] = dict(code=code, unit=items[1], description=items[2],
                                  prices=[number(price) for price in prices],
                                  unit_price=number(prices[0]) if prices else None)
        if tag == 'T' and len(items) >= 2:
            texts[items[0]] = items[1]
        if tag == 'D' and len(items) >= 2:
            parts = items[1].split(slash)
            if parts[-1] == '':
                parts.pop()
            children = decompositions.setdefault(items[0], [])
            if len(parts) == 2:
                children.append(dict(code=parts[0], factor=None, quantity=number(parts[1])))
                warnings.append(f'Descomposición abreviada: {items[0]}')
            else:
                if len(parts) % 3:
                    warnings.append(f'Descomposición incompleta: {items[0]}')
                for idx in range(0, len(parts) - 2, 3):
                    code, factor, quantity = parts[idx:idx + 3]
                    if code:
                        children.append(dict(code=code, factor=number(factor), quantity=number(quantity)))
    if not concepts:
        raise ParseFailure('BC3 sin conceptos ~C válidos')
    for code, concept in concepts.items():
        concept['children'] = decompositions.get(code, [])
        if code in texts:
            concept['text'] = texts[code]
    roots = [code for code in concepts if code.endswith('##')]
    return dict(schema_version='2.0', source_format='FIEBDC-3', encoding=encoding,
                detected_format_version=version, concepts=list(concepts.values()), records=records,
                root_concept_code=roots[0] if len(roots) == 1 else None,
                commercial_unit_price=None, warnings=warnings)


def export_bc3(normalized):
    records = normalized.get('records')
    if not records:
        raise ParseFailure('Reprocesa el archivo para regenerar el BC3')
    txt = ''.join('~' + tag + '|' + '|'.join(fields) + '\r\n' for tag, fields in records)
    return txt.encode(normalized['encoding'])


def parse_epd(blob: bytes):
    try:
        root = etree.fromstring(blob, parser=etree.XMLParser(
            resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False))
    except etree.XMLSyntaxError as exc:
        raise ParseFailure('XML mal formado') from exc
    if root.getroottree().docinfo.doctype:
        raise ParseFailure('DTD y entidades no permitidas')
    if etree.QName(root).localname != 'processDataSet':
        raise ParseFailure('Se esperaba un dataset ILCD de proceso')
    validation = 'STRUCTURAL_ONLY'
    warnings = []
    schema_file = os.environ.get('METRA_EPD_XSD')
    if schema_file:
        try:
            schema = etree.XMLSchema(etree.parse(schema_file, etree.XMLParser(
                resolve_entities=False, no_network=True, load_dtd=False)))
        except (OSError, etree.LxmlError) as exc:
            raise RuntimeError('No se ha podido cargar el XSD local configurado') from exc
        if not schema.validate(root):
            raise ParseFailure('El documento no cumple el XSD ILCD-EPD configurado')
        validation = 'XSD_VALIDATED'
    else:
        warnings.append('Extracción estructural; XSD sin configurar.')
    def nodes(parent, name):
        return parent.xpath('.//*[local-name()=$name]', name=name)
    def first(parent, name):
        return next(iter(nodes(parent, name)), None)
    def content(element):
        return (element.text or '').strip() or None if element is not None else None
    def read(parent, name):
        return content(first(parent, name))
    def localized(element, name):
        if element is None:
            return None
        values = nodes(element, name)
        lang = '{http://www.w3.org/XML/1998/namespace}lang'
        return next((content(e) for e in values if e.get(lang) == 'es'),
                    content(values[0]) if values else None)
    def attr(element, name):
        if element is None:
            return None
        return next((v for k, v in element.attrib.items() if etree.QName(k).localname == name), None)
    def reference(name):
        return localized(first(root, name), 'shortDescription')
    dataset_id = read(root, 'UUID')
    if not dataset_id:
        raise ParseFailure('Falta identificador del conjunto de datos')
    impacts = []
    for category, node_name, ref_name in (
        ('impact', 'LCIAResult', 'referenceToLCIAMethodDataSet'),
        ('resource', 'exchange', 'referenceToFlowDataSet'),
    ):
        for node in nodes(root, node_name):
            ref = first(node, ref_name)
            label = localized(ref, 'shortDescription')
            code_match = re.search(r'\(([^()]+)\)$', label or '')
            unit = localized(first(node, 'referenceToUnitGroupDataSet'), 'shortDescription')
            for amount in nodes(node, 'amount'):
                module = attr(amount, 'module')
                if module:
                    impacts.append(dict(category=category, indicator=code_match[1] if code_match else label,
                                        label=label, indicator_id=attr(ref, 'refObjectId'), module=module,
                                        scenario=attr(amount, 'scenario'), unit=unit, value=content(amount)))
    reference_id = read(root, 'referenceToReferenceFlow')
    flow = next((n for n in nodes(root, 'exchange') if reference_id and
                 n.get('dataSetInternalID') == reference_id), None)
    unit = read(root, 'referenceUnit') or read(root, 'unitName')
    if flow is not None:
        unit = localized(first(flow, 'referenceToUnitGroupDataSet'), 'shortDescription') or unit
    quantity = read(flow, 'meanAmount') if flow is not None else None
    if not unit:
        warnings.append('No se ha identificado la unidad declarada.')
    if not impacts:
        warnings.append('No se han encontrado valores por módulo.')
    nonnumeric = 0
    for impact in impacts:
        if impact['value'] is None:
            continue
        try:
            nonnumeric += not Decimal(impact['value']).is_finite()
        except InvalidOperation:
            nonnumeric += 1
    if nonnumeric:
        warnings.append(f'{nonnumeric} valores por módulo no son números finitos; se conserva el texto original.')
    return dict(schema_version='2.0', source_format='ILCD+EPD', dataset_id=dataset_id,
                ilcd_version=root.get('version'), epd_version=attr(root, 'epd-version'),
                profile=attr(root, 'profile'), name=localized(root, 'baseName'),
                owner=reference('referenceToOwnershipOfDataSet'),
                programme=reference('referenceToPublisher') or reference('referenceToRegistrationAuthority'),
                registration=read(root, 'registrationNumber'),
                publication_date=read(root, 'publicationDateOfEPD') or read(root, 'publicationDate'), valid_until=read(root, 'dataSetValidUntil'),
                country=attr(first(root, 'locationOfOperationSupplyOrProduction'), 'location'),
                declared_unit=dict(quantity=quantity, unit=unit, description=read(root, 'functionalUnitFlowProperties')),
                scenarios=[attr(e, 'name') for e in nodes(root, 'scenario') if attr(e, 'name')],
                impacts=impacts, validation=validation,
                module_count=len({item['module'] for item in impacts}),
                indicator_count=len({item['indicator_id'] or item['indicator'] for item in impacts
                                     if item['indicator_id'] or item['indicator']}),
                verification=dict(status='not_verified_by_platform',
                                  declared_reviewer=reference('referenceToNameOfReviewerAndInstitution')),
                warnings=warnings)


def parse_ifc(blob:bytes):
    try: import ifcopenshell
    except ImportError as e: raise ParseFailure('IfcOpenShell no está disponible') from e
    import tempfile,os
    # Input stays in isolated temporary path; no user controlled filenames.
    with tempfile.NamedTemporaryFile(suffix='.ifc',delete=False) as tmp:
        path=tmp.name;tmp.write(blob)
    try:
        model=ifcopenshell.open(path)
        if not model: raise ParseFailure('IFC ilegible')
        roots=model.by_type('IfcRoot'); ids=[e.GlobalId for e in roots if getattr(e,'GlobalId',None)]
        if len(ids)!=len(set(ids)):raise ParseFailure('GlobalId duplicados')
        from ifcopenshell.util.element import get_psets, get_materials, get_parent, get_aggregate, get_nest
        from ifcopenshell.util.classification import get_references
        products = [e for e in model.by_type('IfcProduct')
                    if not any(e.is_a(kind) for kind in
                               ('IfcSite', 'IfcBuilding', 'IfcBuildingStorey', 'IfcSpace', 'IfcSpatialElement'))]
        total_products = len(products)
        products = products[:IFC_PRODUCT_INDEX_LIMIT]
        product_ids = {e.id() for e in products}
        elements = []
        for e in products:
            parent = get_parent(e)
            aggregate = get_aggregate(e)
            nest = get_nest(e) if aggregate is None else None
            composition_parent = aggregate if aggregate is not None else nest
            material = [m.Name for m in get_materials(e) if getattr(m, 'Name', None)]
            elements.append({
                'id': e.id(), 'global_id': e.GlobalId, 'ifc_class': e.is_a(), 'name': e.Name,
                'parent_id': parent.id() if parent and parent.id() in product_ids else None,
                'composition_parent_id': (composition_parent.id()
                    if composition_parent is not None and composition_parent.id() in product_ids else None),
                'composition_relation': ('IfcRelAggregates' if aggregate is not None else 'IfcRelNests')
                    if composition_parent is not None and composition_parent.id() in product_ids else None,
                'psets': get_psets(e, psets_only=True), 'qto': get_psets(e, qtos_only=True),
                'materials': material,
                'classifications': sorted({str(getattr(ref, 'Identification', None) or
                                               getattr(ref, 'ItemReference', None) or ref.Name)
                                           for ref in get_references(e)}),
                'has_representation': e.Representation is not None,
            })
        warnings=['Lectura de esquema y semántica; geometría sin validación avanzada']
        if total_products>len(elements):
            warnings.append(f'Índice parcial: {len(elements)} de {total_products} productos IFC.')
        return {'schema_version':'2.0','source_format':'IFC','ifc_schema':model.schema,
                'entity_count':sum(1 for _ in model),'roots_count':len(roots),'elements':elements,
                'product_count':total_products,'index_truncated':total_products>len(elements),'warnings':warnings}
    except ParseFailure: raise
    except Exception as e: raise ParseFailure('IFC ilegible o no soportado') from e
    finally:os.unlink(path)

PARSERS={'IFC':parse_ifc,'BC3':parse_bc3,'EPD':parse_epd}
