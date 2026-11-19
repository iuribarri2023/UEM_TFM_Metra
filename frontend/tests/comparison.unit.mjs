import test from 'node:test';
import assert from 'node:assert/strict';
import {MAX_COMPARISON_ITEMS,normalizeComparisonIds,normalizeComparisonKey} from '../src/app/core/comparison-selection.ts';
import {buildComparisonMatrix} from '../src/app/core/comparison-matrix.ts';

const one='11111111-1111-4111-8111-111111111111';
const two='22222222-2222-4222-8222-222222222222';
const three='33333333-3333-4333-8333-333333333333';

test('selección canónica: límite dos, deduplicación y enlaces antiguos',()=>{
  assert.equal(MAX_COMPARISON_ITEMS,2);
  assert.deepEqual(normalizeComparisonIds([one,`g:${two}`,`p:${one}`,three]),[`p:${one}`,`g:${two}`]);
  assert.equal(normalizeComparisonKey(`g:${three}`),`g:${three}`);
  assert.equal(normalizeComparisonKey('g:incorrecto'),null);
  assert.deepEqual(normalizeComparisonIds([]),[]);
});

test('matriz de dos: identificación, tipos mixtos, diferencias, ausencia y EPD no verificadas',()=>{
  const baseline={manufacturer:null,system:'Envolvente',system_id:'s1',subsystem:'Fachada',subsystem_id:'sub1',
    functional_unit:'m²',revision:null,status:'PUBLISHED',assets:[],bim_status:'NO_IFC',
    economic_data:{price:{value:20,unit:'€/m²',source:'BC3 declarado'}},
    environmental_data:{gwp:{value:10,unit:'kg CO2e',source:'EPD no verificada'}},
    composition:[{name_es:'Capa',properties:{thickness_mm:50}}]};
  const a={...baseline,key:`g:${one}`,id:one,kind:'generic',code:'G1',name:'Referencia',
    technical_data:{u:{value:1.2,unit:'W/m²K',source:'Ensayo A'},only_left:8}};
  const b={...baseline,key:`p:${two}`,id:two,kind:'commercial',code:'P2',name:'Producto',
    status:'APPROVED',revision:2,manufacturer:'Fabricante',technical_data:{u:{value:0.9,unit:'W/m²K',source:'Ensayo B'}}};
  const rows=buildComparisonMatrix({solutions:[a,b],warnings:[],same_subsystem:true,same_functional_unit:true});
  const prestations=rows.find(section=>section.title==='Prestaciones').rows;
  assert.match(prestations.find(row=>row.key==='u').note,/Diferente/);
  assert.equal(prestations.find(row=>row.key==='only_left').note,'Dato no declarado');
  const economics=rows.find(section=>section.title==='Economía').rows;
  assert.equal(economics.find(row=>row.key==='price').different,false);
  const env=rows.find(section=>section.title==='Ambiente').rows;
  assert.match(env.find(row=>row.key==='gwp').note,/Verificar EPD/);
  assert.equal(rows.find(section=>section.title==='Identificación').rows.find(row=>row.key==='Tipo').different,true);
});

test('no calcular diferencias numéricas para distintas unidades funcionales',()=>{
  const common={key:`g:${one}`,id:one,kind:'generic',name:'A',code:'A',manufacturer:null,system:null,system_id:'x',subsystem:null,
    subsystem_id:'x',functional_unit:'m²',revision:null,status:'PUBLISHED',technical_data:{},composition:[],
    economic_data:{cost:{value:12,unit:'€'}},environmental_data:{},assets:[],bim_status:'NO_IFC'};
  const second={...common,key:`p:${two}`,kind:'commercial',name:'B',code:'B',functional_unit:'m³',
    economic_data:{cost:{value:15,unit:'€'}}};
  const rows=buildComparisonMatrix({solutions:[common,second],warnings:[],same_subsystem:true,same_functional_unit:false});
  assert.match(rows.find(x=>x.title==='Economía').rows.find(r=>r.key==='cost').note,/no equivalente/);
});
