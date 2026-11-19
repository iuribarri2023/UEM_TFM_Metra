"""Deterministic reference estimates. Coefficients are modelling assumptions."""
from pathlib import Path
import sys
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.consolidated_data import academic_value
from scripts.consolidate_data import documents, write, BACKEND

ROOT = BACKEND/'data/metra-demo'
# Reference mass per functional unit, material EUR/kg, production kgCO2e/kg,
# installation labour h/FU, lifting equipment h/FU.
PROFILES = {
    'ENV.FAC': (78,.83,.71,1.25,.20), 'ENV.CUB': (110,.55,.47,1.05,.17),
    'ENV.VEN': (32,3.50,2.50,1.65,.12), 'EST.FOR': (190,.43,.48,.95,.45),
    'EST.MUR': (155,.48,.45,1.30,.32), 'INT.PAR': (33,.86,.43,.82,.04),
    'INT.TRA': (22,.95,.48,.66,.03), 'INT.SUE': (55,.90,.60,.78,.04),
    'MOD.BAN': (1350,1.45,.86,14,2.8),
}
ENERGY_PER_KG = dict(zip(PROFILES,(9,6,30,5,5,8,8,9,14)))
METHOD = 'METRA-REF-2026-01'


def money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def measure(performance, key, unit):
    cell=performance.get(key) or {}
    v=cell.get('value')
    return v if type(v) in (int,float) and v>0 and cell.get('unit')==unit else None


def model(record, subsystem):
    base, rate, factor, hours, equipment = PROFILES[subsystem]
    unit=record['functional_unit']
    p=record['technical_performance']
    mass=measure(p,'surface_mass','kg/m²') if unit=='m2' else None
    kind='p' if 'subsystem_code' in record else 'g'
    # Existing generated values are estimates. They are not used as measured inputs.
    if mass and academic_value(kind,record['code'],'/technical_performance/surface_mass/value',mass):
        mass=None
    thickness=measure(p,'total_thickness_mm','mm') or measure(p,'depth_mm','mm')
    if thickness and any(academic_value(kind,record['code'],f'/technical_performance/{key}/value',thickness)
                         for key in ('total_thickness_mm','depth_mm')):
        thickness=None
    assumed=base
    if thickness and unit=='m2':
        assumed=base * max(.55,min(2.1,thickness/180))
    mass=round(mass or assumed,3)
    scale=max(.6,min(1.8,(mass/base)**.35))
    components = [
        ('Materiales',mass,'kg',rate), ('Mano de obra',round(hours*scale,3),'h',32),
        ('Montaje',round(hours*.28*scale,3),'h',37), ('Maquinaria',equipment,'h',49),
        ('Transporte',round(mass/1000*100,5),'t·km',.14),
    ]
    items=[{'label':name,'quantity':qty,'unit':u,'rate':price,'subtotal':money(qty*price)}
           for name,qty,u,price in components]
    direct=sum(line['subtotal'] for line in items)
    items.append({'label':'Auxiliares','quantity':1,'unit':'lote','rate':money(direct*.05),
                  'subtotal':money(direct*.05)})
    common={'method':METHOD,'functional_unit':unit,'quantity':1,'subsystem':subsystem}
    cost={**common,'currency':'EUR','scope':'suministro-transporte-montaje',
          'location':'España · base convencional','period':'2026-01','items':items,
          'total':money(sum(line['subtotal'] for line in items))}
    production=round(mass*factor,3)
    delivery=round(mass/1000*100*.10,3)
    modules=[{'module':'A1–A3','value':production},{'module':'A4','value':delivery}]
    environment={**common,'scope':'producción-transporte','indicator':'GWP','unit':'kg CO₂e',
                 'modules':modules,'total':round(production+delivery,3),
                 'additional':[{'label':'Energía primaria estimada','module':'A1–A3','unit':'MJ',
                                'value':round(mass*ENERGY_PER_KG[subsystem],3)}]}
    return cost,environment



def describe(record, catalogue):
    """Recover missing descriptive fields from recorded classification and layers."""
    fields=record['technical_performance']
    def put(key,value):
        target=fields.get(key)
        if target and target['value'] is None and isinstance(value,str) and value.strip():
            target.update(value=value,source_type='CALCULATED')
    archetype=catalogue.get('archetype') or {}
    put('system_type',archetype.get('name_es'))
    declared=[]
    for layer in record['composition']:
        if not isinstance(layer,dict) or layer.get('source_type')=='ESTIMATED':
            continue
        details=layer.get('properties') or {}
        material=layer.get('material') or details.get('material_family')
        thickness=layer.get('thickness_mm',details.get('thickness_mm'))
        role=layer.get('role','')
        name=layer.get('name_es') or layer.get('name')
        if role in ('waterproofing','waterproofing_membrane'):
            put('waterproofing',name)
        if role in ('surface_finish','floor_finish','floor_covering'):
            put('surface_finish',material or name)
        if isinstance(material,str) and material not in ('other','air','unknown') and role!='air_cavity' and type(thickness) in (int,float) and thickness>0:
            declared.append((thickness,material))
    if declared and sum(thickness==max(item[0] for item in declared) for thickness,_ in declared)==1:
        put('primary_material',max(declared)[1])

def complete(root=ROOT):
    for group,path,doc in documents(root):
        for row in doc[group]:
            subsystem=row.get('subsystem_code') or doc['catalogue']['subsystem']['code']
            p=row['technical_performance']
            # Derive total only when every layer has an explicit positive thickness.
            if not row['composition']:
                row['composition']=[{**part,'source_type':'ESTIMATED'}
                                    for part in row.get('composition_scenario',{}).get('elements',[])]
            layers=row['composition']
            thicknesses=[layer.get('thickness_mm',(layer.get('properties') or {}).get('thickness_mm'))
                         for layer in layers if isinstance(layer,dict)]
            total=p.get('total_thickness_mm')
            if total and total['value'] is None and thicknesses and len(layers)==len(thicknesses) and not any(layer.get('source_type')=='ESTIMATED' for layer in layers) and all(
                    type(value) in (int,float) and value>0 for value in thicknesses):
                total.update(value=round(sum(thicknesses),3),source_type='CALCULATED')
            if not row.get('description'):
                row['description']=row['name_es']
            describe(row,doc.get('catalogue',{}))
            cost,environment=model(row,subsystem)
            row['economic_data']['reference']=cost
            row['environmental_data']['reference']=environment
        write(path,doc)


if __name__=='__main__':
    complete()
