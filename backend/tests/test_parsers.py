from app.parsers import parse_bc3,parse_epd,ParseFailure
import pytest

def test_bc3_concept_and_no_inferred_price():
    result=parse_bc3(b'~V|FILE|3/2024|~C|WALL|m2|Test facade|124.50|~C|INNER|kg|Layer|12.4|~D|WALL|INNER\\2.0\\|')
    assert result['concepts'][0]['unit_price']==124.5
    assert result['commercial_unit_price'] is None
    assert result['concepts'][0]['children'][0]['quantity']==2.0

def test_bc3_invalid():
    with pytest.raises(ParseFailure):parse_bc3(b'totally different file')

def test_xml_xxe_blocked():
    with pytest.raises(ParseFailure):parse_epd(b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><processDataSet><UUID>&e;</UUID></processDataSet>')

def test_epd_partial_profile_discloses_verification():
    d=parse_epd(b'<processDataSet><UUID>1234</UUID><referenceUnit>m2</referenceUnit></processDataSet>')
    assert d['verification']['status']=='not_verified_by_platform'
    assert d['declared_unit']['unit']=='m2'


def test_demo_ifc_geometry_and_property_set():
    import ifcopenshell
    import ifcopenshell.geom
    from pathlib import Path
    from app.parsers import parse_ifc
    fixture=Path(__file__).resolve().parents[1]/'tests/fixtures/panel_demo.ifc'
    result=parse_ifc(fixture.read_bytes())
    assert [element['ifc_class'] for element in result['elements']]==['IfcWall']
    assert result['elements'][0]['psets']['Pset_METRA_Demo']['Thickness_mm']==200
    model=ifcopenshell.open(str(fixture))
    shape=ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(),model.by_type('IfcWall')[0])
    assert len(shape.geometry.verts)>0



def test_ifc_composition_relations_from_source(tmp_path,monkeypatch):
    import ifcopenshell
    from pathlib import Path
    from app.parsers import parse_ifc

    source=Path(__file__).resolve().parents[1]/'tests/fixtures/panel_demo.ifc'
    model=ifcopenshell.open(str(source))
    panel=next(item for item in model.by_type('IfcProduct') if item.Name=='Panel de ensayo')
    assembly=model.create_entity('IfcElementAssembly',GlobalId=ifcopenshell.guid.new(),Name='Ensamblaje')
    nested=model.create_entity('IfcBuildingElementProxy',GlobalId=ifcopenshell.guid.new(),Name='Pieza anidada')
    model.create_entity('IfcRelAggregates',GlobalId=ifcopenshell.guid.new(),
                        RelatingObject=assembly,RelatedObjects=[panel])
    model.create_entity('IfcRelNests',GlobalId=ifcopenshell.guid.new(),
                        RelatingObject=panel,RelatedObjects=[nested])
    path=tmp_path/'relations.ifc'
    model.write(str(path))
    elements={element['global_id']:element for element in parse_ifc(path.read_bytes())['elements']}
    assert elements[panel.GlobalId]['composition_parent_id']==assembly.id()
    assert elements[panel.GlobalId]['composition_relation']=='IfcRelAggregates'
    assert elements[nested.GlobalId]['composition_parent_id']==panel.id()
    assert elements[nested.GlobalId]['composition_relation']=='IfcRelNests'
    from app import parsers
    monkeypatch.setattr(parsers,'IFC_PRODUCT_INDEX_LIMIT',1)
    partial=parse_ifc(path.read_bytes())
    assert partial['index_truncated'] and len(partial['elements'])==1
    assert partial['product_count']==len(elements)
