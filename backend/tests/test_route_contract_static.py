from pathlib import Path
import ast

def test_no_legacy_demo_endpoints():
    source=(Path(__file__).resolve().parents[1]/'app/api.py').read_text()
    assert '/marketplace/demo/' not in source
    assert 'api_fase3_v1' not in source

def test_openapi_matches_registered_blueprint_methods():
    import json,re
    source=Path(__file__).resolve().parents[1]/'app/api.py'
    expected=[]
    modules=['api_support.py','asset_service.py','economics.py','documents.py','component_links.py']
    modules.extend(str(p.relative_to(source.parent)) for p in (source.parent/'routes').glob('*.py'))
    nodes=[node for module in modules for node in ast.parse((source.parent/module).read_text()).body]
    for node in nodes:
        if not isinstance(node,ast.FunctionDef):continue
        for d in node.decorator_list:
            if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and isinstance(d.func.value,ast.Name) and d.func.value.id=='api':
                expected.append((d.func.attr,'/api/v1'+re.sub(r'<(?:\w+:)?(\w+)>',r'{\1}',ast.literal_eval(d.args[0]))))
    openapi=json.loads((source.parents[1]/'openapi.json').read_text())
    assert all(m in openapi['paths'][p] for m,p in expected)
    assert len(expected)>=70
    assert not any('price-books' in path for path in openapi['paths'])


def test_openapi_exact_registered_api_v1_methods():
    import json
    import re
    from app import create_app

    application = create_app({'TESTING':True})
    declared = json.loads((Path(__file__).resolve().parents[1] / 'openapi.json').read_text())['paths']
    documented = {(path, method) for path, operations in declared.items() for method in operations
                  if method in {'get','post','put','patch','delete'} and path.startswith('/api/v1/')}
    registered = {(re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', rule.rule), method.lower())
                  for rule in application.url_map.iter_rules() if rule.rule.startswith('/api/v1/')
                  for method in rule.methods - {'HEAD','OPTIONS'}}
    assert registered == documented
