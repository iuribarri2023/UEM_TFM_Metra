import type {CanonicalSolution} from './canonical';
/** Comparison of *declared* values; never converts units or assumes EPD equivalence. */
export interface ComparedAsset {
  id:string;file_type:string;original_name:string;processing_status:string;
  thumbnail_available?:boolean;public_view_allowed?:boolean;public_download_allowed?:boolean;
}
export interface ComparedSolution {
  canonical?:CanonicalSolution;key:string;id:string;kind:'generic'|'commercial';name:string;code:string;
  manufacturer:string|null;system:string|null;system_id:string|null;
  subsystem:string|null;subsystem_id:string;functional_unit:string|null;
  revision:number|null;status:string;technical_data:unknown;composition:unknown;
  economic_data:unknown;environmental_data:unknown;assets:ComparedAsset[];bim_status:string;
}
export interface ComparedResult {solutions:[ComparedSolution,ComparedSolution];warnings:string[];same_subsystem:boolean;same_functional_unit:boolean}
export type SectionName='Identificación'|'Prestaciones'|'Composición'|'BIM'|'Economía'|'Ambiente'|'Documentación';
export const COMPARISON_SECTIONS:SectionName[]=['Identificación','Prestaciones','Composición','BIM','Economía','Ambiente','Documentación'];
export interface CompareCell {value:string;unit:string;source:string;raw:number|null}
export interface ComparisonRow {key:string;label:string;a:CompareCell;b:CompareCell;different:boolean;note:string}
export interface ComparisonSection {title:SectionName;rows:ComparisonRow[]}

const OMIT=new Set(['illustrative','reference','schema_version','legacy_payload','legacy_source','publication_rights','source_references','viva_metrics']);
const empty:CompareCell={value:'—',unit:'',source:'',raw:null};
function plain(value:unknown):string {
  if(value===null||value===undefined||value==='')return '—';
  if(typeof value==='string')return value.trim()||'—';
  if(typeof value==='number'&&Number.isFinite(value))return String(value);
  if(typeof value==='boolean')return value?'Sí':'No';
  return '—';
}
function cell(value:unknown,unit='',source=''):CompareCell {
  return {value:plain(value),unit:plain(unit)==='—'?'':plain(unit),source:plain(source)==='—'?'':plain(source),
    raw:typeof value==='number'&&Number.isFinite(value)?value:null};
}
function object(value:unknown):Record<string,unknown>|null {
  return value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:null;
}
/** Flatten only actual declared fields. Keep labels, units and local provenance intact. */
export function flattenDeclared(value:unknown):Map<string,CompareCell> {
  const records=new Map<string,CompareCell>();
  function walk(node:unknown,path:string,source:string,depth:number){
    if(depth>8||node===null||node===undefined)return;
    if(Array.isArray(node)){
      node.forEach((item,index)=>walk(item,`${path} / ${index+1}`,source,depth+1));return;
    }
    const row=object(node);
    if(row){
      if('value' in row&&!object(row['value'])&&!Array.isArray(row['value'])){
        records.set(path||plain(row['name_es']||row['name']||row['label']),cell(row['value'],row['unit'] as string,
          (row['source']||row['standard']||row['method']||source) as string));return;
      }
      const provenance=plain(row['source']||row['provenance']||source);
      for(const [key,sub] of Object.entries(row)){
        if(OMIT.has(key)||key==='source'||key==='provenance'||key==='unit'||key==='method'||key==='standard')continue;
        walk(sub,path?`${path} / ${key}`:key,provenance==='—'?'':provenance,depth+1);
      }
      return;
    }
    records.set(path,cell(node,'',source));
  }
  walk(value,'','',0);
  return records;
}
function mapValues(values:Record<string,unknown>){
  return new Map(Object.entries(values).map(([key,value])=>[key,cell(value)]));
}
function assetsMap(solution:ComparedSolution){
  const out=new Map<string,CompareCell>();
  for(const type of ['IFC','BC3','EPD']){
    const files=solution.assets.filter(asset=>asset.file_type===type);
    out.set(type,cell(files.length?files.map(file=>`${file.original_name} (${file.processing_status}; ${file.public_view_allowed?'vista autorizada':'sin vista pública'}; ${file.public_download_allowed?'descarga autorizada':'sin descarga pública'})`).join('; '):null));
  }
  return out;
}
function sectionRows(title:SectionName,left:Map<string,CompareCell>,right:Map<string,CompareCell>,pair:ComparedResult):ComparisonRow[]{
  return [...new Set([...left.keys(),...right.keys()])].sort((a,b)=>a.localeCompare(b,'es')).map(key=>{
    const a=left.get(key)||empty, b=right.get(key)||empty;
    const absent=a.value==='—'||b.value==='—';
    const mismatch=a.value!==b.value||a.unit!==b.unit||a.source!==b.source;
    const compatibleUnit=a.unit===b.unit;
    const compatibleFunction=pair.same_subsystem&&pair.same_functional_unit;
    let note=absent?'Dato no declarado':!compatibleUnit?'Unidades distintas · no comparable':a.value===b.value&&a.source!==b.source?'Procedencias distintas':mismatch?'Diferente':'Coincide';
    // Environmental comparisons demand external EPD-scope/method checks. No numerical conclusions.
    if(title==='Ambiente'&&!absent)note='Verificar EPD, módulo, indicador, alcance, fuente y método';
    if(title==='Economía'&&!absent&&!compatibleFunction)note='Unidad funcional o subsistema no equivalente';
    if(title==='Prestaciones'&&!absent&&!pair.same_subsystem)note='Distinto subsistema · equivalencia no verificada';
    if(title==='Economía'&&!absent&&compatibleFunction&&a.source!==b.source)note='Fuentes distintas · diferencia cuantitativa no calculada';
    if(title==='Economía'&&!absent&&compatibleFunction&&mismatch)
      note='Revisar fecha, método y alcance antes de cuantificar una diferencia';
    return {key,label:key.replaceAll(' / ',' · '),a,b,different:absent||mismatch,note};
  });
}
export function buildComparisonMatrix(pair:ComparedResult):ComparisonSection[]{
  const [a,b]=pair.solutions;
  const identification=(s:ComparedSolution)=>mapValues({
    'Nombre':s.name,'Código':s.code,'Tipo':s.kind==='generic'?'Genérica':'Comercial',
    'Fabricante':s.manufacturer,'Sistema':s.system,'Subsistema':s.subsystem,
    'Unidad funcional':s.functional_unit,'Versión publicada':s.revision,'Estado':s.status,
  });
  const bim=(s:ComparedSolution)=>mapValues({'Estado BIM':s.bim_status,
    'IFC públicos visibles':s.assets.filter(asset=>asset.file_type==='IFC'&&asset.public_view_allowed&&asset.processing_status==='VALID').length});
  const domains:[SectionName,(s:ComparedSolution)=>Map<string,CompareCell>][]=[
    ['Identificación',identification],['Prestaciones',s=>s.canonical
      ? new Map(s.canonical.template.fields.map(field=>{
          const value=s.canonical!.properties[field.code];
          const source=value.source_type==='DEMO_SIMULATED'?'Valor estimado':value.source_type==='SOURCE_DECLARED'?'Fuente declarada':'';
          return [field.code,cell(value.value,value.unit,source)];
        }))
      : flattenDeclared(s.technical_data)],
    ['Composición',s=>flattenDeclared(s.composition)],['BIM',bim],
    ['Economía',s=>flattenDeclared(s.economic_data)],['Ambiente',s=>flattenDeclared(s.environmental_data)],
    ['Documentación',assetsMap]
  ];
  const labels=new Map(a.canonical?.template.fields.map(field=>[field.code,field.name_es||field.label||field.code])||[]);
  return domains.map(([title,read])=>({title,rows:sectionRows(title,read(a),read(b),pair).map(row=>
    title==='Prestaciones'&&labels.has(row.key)?{...row,label:labels.get(row.key)!}:row)}));
}
