import {Component,Input,OnChanges} from '@angular/core';
import {humanizeTechnicalPath,esNumber,sourceTitle} from '../core/technical-terminology';

interface ValueRow {label:string;value:string;unit:string;source:string}
interface ValueGroup {label:string;rows:ValueRow[]}
const METADATA=new Set(['schema_version','legacy_source','legacy_payload','publication_rights','generated_for','source_type','verification_status','methodology']);

function record(value:unknown):Record<string,unknown>|undefined {
  return value!==null&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:undefined;
}
function literal(value:unknown):string {
  if(typeof value==='string')return value.trim()||'—';
  if(typeof value==='number')return esNumber(value,6);
  if(typeof value==='boolean')return value?'Sí':'No';
  return '—';
}
function collect(value:unknown,label:string,source:string,depth=0):ValueRow[] {
  if(depth>5)return [];
  if(Array.isArray(value)){
    return value.flatMap((item,index)=>collect(item,label+' '+(index+1),source,depth+1));
  }
  const obj=record(value);
  if(!obj)return [{label:humanizeTechnicalPath(label),value:literal(value),unit:'—',source:sourceTitle(source)}];
  if('value' in obj&&(!obj['value']||typeof obj['value']!=='object')){
    const named=literal(obj['label']??obj['name_es']??obj['name']);
    const provenance=literal(obj['source']??obj['standard']??obj['method']);
    return [{label:humanizeTechnicalPath(named==='—'?label:named),value:literal(obj['value']),unit:literal(obj['unit']),
      source:sourceTitle(provenance==='—'?source:provenance)}];
  }
  return Object.entries(obj).filter(([key])=>!METADATA.has(key)).flatMap(([key,child])=>
    collect(child,label?label+' / '+key:key,source,depth+1));
}

@Component({selector:'app-declared-values',standalone:true,template:`
@for(group of groups;track group.label){
  <section class="declared-value-group" [attr.aria-label]="group.label">
    <h3>{{group.label}}</h3>
    <div class="technical-scroll"><table class="work-table">
      <thead><tr><th scope="col">Magnitud</th><th scope="col">Valor</th><th scope="col">Unidad</th><th scope="col">Origen</th></tr></thead>
      <tbody>@for(row of group.rows;track $index){
        <tr><th scope="row">{{row.label}}</th><td>{{row.value}}</td><td>{{row.unit}}</td><td>{{row.source}}</td></tr>
      }</tbody>
    </table></div>
  </section>
}@empty{<p class="muted">{{empty}}</p>}
`})
export class DeclaredValuesComponent implements OnChanges {
  @Input() values:unknown;
  @Input() label='Datos declarados en la ficha';
  @Input() empty='Sin datos estructurados declarados.';
  groups:ValueGroup[]=[];
  ngOnChanges(){
    const source=record(this.values)||{};
    const current=Object.fromEntries(Object.entries(source).filter(([key])=>key!=='legacy'&&!METADATA.has(key)));
    const groups=[
      {label:this.label,rows:collect(current,'','Ficha')},
      {label:'Datos históricos importados',rows:source['legacy']!=null?collect(source['legacy'],'','Catálogo METRA-DEMO'):[]}
    ];
    this.groups=groups.filter(group=>group.rows.length);
  }
}
