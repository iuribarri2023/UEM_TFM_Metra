from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

import pytest

from app.catalogue import TemplateProjectionIntegrityError, project
from app.data_templates import fields_for
from app.models import Subsystem


def _db(latest):
    sub=SimpleNamespace(id=uuid4(),code='ENV.FAC',system_id=uuid4())
    system=SimpleNamespace(id=sub.system_id,code='ENV')
    db=Mock()
    db.get.side_effect=lambda model,id:sub if model is Subsystem else system
    db.scalar.side_effect=[None,latest]
    return db,sub


def test_missing_historical_template_falls_back_with_warning_and_keeps_capture_version():
    latest=SimpleNamespace(version=4,fields=fields_for('ENV.FAC'))
    db,sub=_db(latest)
    item=SimpleNamespace(id=uuid4(),code='P1',subsystem_id=sub.id)
    record={'id':str(uuid4()),'name_es':'Historical','template_version':2,'technical_data':{}}
    result=project(db,item,record,'commercial')
    assert result['template']['version']==4
    assert result['traceability']['capture_template_version']==2
    assert result['traceability']['effective_template_version']==4
    assert result['quality']['warnings']==[{'code':'HISTORICAL_TEMPLATE_FALLBACK',
        'requested_version':2,'effective_version':4,'subsystem_code':'ENV.FAC'}]
    assert record['template_version']==2


def test_missing_historical_template_without_fallback_is_controlled_error():
    db,sub=_db(None)
    item=SimpleNamespace(id=uuid4(),code='P1',subsystem_id=sub.id)
    with pytest.raises(TemplateProjectionIntegrityError):
        project(db,item,{'template_version':2,'technical_data':{}},'commercial')
