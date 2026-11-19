from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from typing import Annotated, Literal
import math
import re
from .parsers import ParseFailure

class RegisterDTO(BaseModel):
    email:EmailStr
    password:str=Field(min_length=12,max_length=128)
    manufacturer_name:str=Field(min_length=2,max_length=255)

class InviteAcceptDTO(BaseModel):
    token:str=Field(min_length=20)
    email:EmailStr
    password:str=Field(min_length=12,max_length=128)

class LoginDTO(BaseModel):
    email:EmailStr
    password:str

class ProductDTO(BaseModel):
    subsystem_id:str
    code:str=Field(min_length=3,max_length=100,pattern=r'^[A-Za-z0-9._-]+$')
    name_es:str=Field(min_length=2,max_length=255)
    commercial_reference:str=''
    functional_unit:str=Field(default='unit',max_length=24)
    description:str=''
    technical_data:dict=Field(default_factory=dict)
    generic_solution_ids:list[str]=Field(default_factory=list)

class CompositionLayer(BaseModel):
    name: str = Field(min_length=1, max_length=180, pattern=r'\S')
    material: str = Field(default='', max_length=180)
    thickness_mm: float | None = Field(default=None, gt=0, le=100000)


class DeclaredValue(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    label: str = Field(min_length=1, max_length=180, pattern=r'\S')
    value: Annotated[str, Field(min_length=1, max_length=500)] | float
    unit: str = Field(default='', max_length=60)
    source: str = Field(default='', max_length=180)


class RevisionDTO(BaseModel):
    name_es:str=Field(min_length=2,max_length=255)
    commercial_reference:str=''
    description:str=''
    functional_unit:str=Field(min_length=1,max_length=24)
    technical_data:dict=Field(default_factory=dict)
    composition: list[CompositionLayer] | None = Field(default=None, max_length=100)
    economic_values: list[DeclaredValue] | None = Field(default=None, max_length=100)
    environmental_values: list[DeclaredValue] | None = Field(default=None, max_length=100)
    generic_solution_ids:list[str]=Field(default_factory=list)

class CatalogueDTO(BaseModel):
    code:str=Field(min_length=2,max_length=110,pattern=r'^[A-Za-z0-9._-]+$')
    name_es:str=Field(min_length=2,max_length=255)
    system_id:str|None=None
    subsystem_id:str|None=None
    archetype_id:str|None=None
    technical_data:dict=Field(default_factory=dict)
    composition:list=Field(default_factory=list)

class TemplateDTO(BaseModel):
    subsystem_id:str
    fields:list[dict]=Field(max_length=250)

    @field_validator('fields')
    @classmethod
    def validate_fields(cls, fields):
        seen = set()
        for field in fields:
            code = field.get('code')
            if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', code) or code in seen:
                raise ValueError('Cada campo requiere un código único y válido')
            seen.add(code)
            if field.get('type') not in ('number', 'string', 'text', 'boolean'):
                raise ValueError(f'{code}: tipo no admitido')
            if not isinstance(field.get('unit'), str) or not field['unit']:
                raise ValueError(f'{code}: unidad obligatoria')
            for key in ('min', 'max'):
                if key in field and (type(field[key]) not in (int,float) or abs(field[key])>1e15 or not math.isfinite(field[key])):
                    raise ValueError(f'{code}: límite inválido')
            if 'min' in field and 'max' in field and field['min'] > field['max']:
                raise ValueError(f'{code}: intervalo inválido')
        return fields

ALLOWED_UNITS={'m','m2','m3','kg','unit','ud','pcs','equipment','kW','W','Pa','mm','cm','%','kgCO2e'}
def check_template(template,properties):
    errors=[]
    for field in template.fields:
        key=field.get('code'); required=field.get('required',False)
        val=properties.get(key)
        if required and (val is None or val=='' or isinstance(val,dict) and val.get('value') in (None,'')):errors.append(f'Falta propiedad obligatoria: {key}');continue
        if val is None:continue
        if not isinstance(val,dict) or 'value' not in val or 'unit' not in val:
            errors.append(f'{key}: se requiere value y unit');continue
        if val['unit']!=field.get('unit','unit'):errors.append(f'{key}: unidad esperada {field.get("unit","unit")}')
        if field.get('type')=='number':
            if type(val['value']) not in (int,float) or abs(val['value'])>1e15 or not math.isfinite(val['value']):errors.append(f'{key}: valor no numérico')
            elif ('min' in field and val['value']<field['min']) or ('max' in field and val['value']>field['max']):errors.append(f'{key}: fuera de rango')
        if field.get('type') in ('string','text') and not isinstance(val['value'],str):
            errors.append(f'{key}: se requiere texto')
        if field.get('type')=='boolean' and type(val['value']) is not bool:
            errors.append(f'{key}: se requiere un booleano')
        if field.get('enum') and val['value'] not in field['enum']:errors.append(f'{key}: fuera de enumeración')
    return errors

def discrepancies(template,props,ifc_data):
    issues=[]
    # Only explicitly mapped IFC fields, never arbitrary fuzzy Pset comparisons.
    for field in template.fields:
        mapping=field.get('ifc_mapping')
        if not mapping or field.get('code') not in props:continue
        # Available in explicit preprocessed observations, not guessed from element names.
        observed=ifc_data.get('mapped_properties',{}).get(mapping)
        if observed is None and isinstance(mapping,str) and '.' in mapping:
            pset,prop=mapping.split('.',1)
            values={str(element['psets'][pset][prop]) for element in ifc_data.get('elements',[])
                    if prop in element.get('psets',{}).get(pset,{})
                    and element['psets'][pset][prop] is not None}
            if len(values)==1:
                observed=values.pop()
        prop=props[field['code']]
        declared=prop.get('value') if isinstance(prop,dict) else None
        if observed is not None and declared is not None and str(observed)!=str(declared):
            issues.append({'code':field['code'],'declared':declared,'ifc_value':observed,'mapping':mapping,'blocking':True})
    return issues
