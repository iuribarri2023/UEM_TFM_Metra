"""Isolated parser checks that can run without the Flask service installed."""
from importlib.util import spec_from_file_location,module_from_spec
from pathlib import Path
import pytest
source=Path(__file__).resolve().parents[1]/'app'/'parsers.py'
spec=spec_from_file_location('isolated_parsers',source)
module=module_from_spec(spec);spec.loader.exec_module(module)

def test_bc3_valid_concepts_and_ambiguous_price():
    d=module.parse_bc3(b'~V|sample|3/2024|~C|PANEL|m2|Panel|40,00|~D|PANEL|LAYER\\1.5\\|')
    assert d['concepts'][0]['unit_price']==40.0
    assert d['commercial_unit_price'] is None
    assert d['concepts'][0]['children'][0]['quantity']==1.5

def test_bc3_bad_input():
    with pytest.raises(module.ParseFailure):module.parse_bc3(b'no data')

def test_epd_minimal_profile():
    d=module.parse_epd(b'<processDataSet><UUID>demo</UUID><referenceUnit>m2</referenceUnit></processDataSet>')
    assert d['dataset_id']=='demo'
    assert d['verification']['status']=='not_verified_by_platform'

def test_epd_xxe():
    with pytest.raises(module.ParseFailure):module.parse_epd(b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><processDataSet><UUID>&e;</UUID></processDataSet>')


def test_bcca_real_round_trip():
    example=source.parents[1]/'tests/fixtures/BCCA2023_V02.zip'
    parsed=module.parse_bc3(example.read_bytes())
    assert len(parsed['concepts'])==15514
    assert parsed['detected_format_version']=='FIEBDC-3/2020'
    assert parsed['root_concept_code']=='BCCA_2023_v02##'
    concepts={c['code']:c for c in parsed['concepts']}
    assert concepts['-AUX#']['children'][0]==dict(code='AA.',factor=1.0,quantity=1.0)
    assert module.parse_bc3(module.export_bc3(parsed))==parsed


def test_bc3_rejects_unsafe_zip():
    from io import BytesIO
    from zipfile import ZipFile
    data=BytesIO()
    with ZipFile(data,'w') as archive:
        archive.writestr('../sample.bc3','~C|ITEM|m|Item|10|')
    with pytest.raises(module.ParseFailure):
        module.parse_bc3(data.getvalue())


def test_lignum_real_modules_and_absences():
    parsed=module.parse_epd((source.parents[1]/'tests/fixtures/lignum.xml').read_bytes())
    assert parsed['profile']=='EN_15804_A2'
    assert parsed['publication_date']=='2022-09-27'
    assert parsed['valid_until']=='2027'
    assert len(parsed['impacts'])==221
    assert any(i['indicator']=='GWP-total' and i['module']=='A1-A3' and
               i['value']=='-62.1' and i['unit']=='kg CO2-Äqv.' for i in parsed['impacts'])
    assert any(i['value'] is None for i in parsed['impacts'])


def test_epd_local_schema_is_applied(monkeypatch,tmp_path):
    schema=tmp_path/'fixture.xsd'
    schema.write_text("""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    <xs:element name="processDataSet">
      <xs:complexType><xs:sequence><xs:element name="UUID" type="xs:string"/></xs:sequence></xs:complexType>
    </xs:element></xs:schema>""")
    monkeypatch.setenv('METRA_EPD_XSD',str(schema))
    accepted=module.parse_epd(b'<processDataSet><UUID>demo</UUID></processDataSet>')
    assert accepted['validation']=='XSD_VALIDATED'
    assert accepted['verification']['status']=='not_verified_by_platform'
    with pytest.raises(module.ParseFailure,match='XSD'):
        module.parse_epd(b'<processDataSet><UUID>demo</UUID><unexpected/></processDataSet>')
