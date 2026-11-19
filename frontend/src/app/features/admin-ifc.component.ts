import {Component,inject,OnInit,signal} from '@angular/core';
import {RouterLink} from '@angular/router';
import {FormsModule} from '@angular/forms';
import {ApiService,problem} from '../core/api';
import {ViewerHostComponent} from './viewer-host.component';

type Intent='unchanged'|'allow'|'deny';
interface IfcRow {kind:'generic'|'commercial';target_id:string;code:string;name:string;manufacturer?:string;solution_status:string;revision?:number;asset_id:string;original_name:string;processing_status:string;integrity_status:string;last_permission_change_at?:string|null;sha256:string;public_view_allowed:boolean;public_download_allowed:boolean}
interface Change {asset_id:string;updated:boolean;code?:string;message?:string}
interface Target {kind:'generic'|'commercial';target_id:string;asset_id:string;expected:{public_view_allowed:boolean;public_download_allowed:boolean};policy:{public_view_allowed:boolean;public_download_allowed:boolean;rights_evidence:string}}
interface Review {targets:Target[];excluded:string[];viewOn:number;viewOff:number;downloadOn:number;downloadOff:number;evidence:string}
interface Integrity {status:string;expected_sha256:string;actual_sha256:string|null;extraction_valid:boolean|null;representable_elements:number}
interface History {id:string;at:string;actor_id:string;detail:{before:boolean[];after:boolean[];evidence?:string}}

@Component({standalone:true,imports:[FormsModule,RouterLink,ViewerHostComponent],template:`
<div class="container content portal-content">
  <div class="portal-page-title"><span class="eyebrow">ADMINISTRACIÓN / IFC</span><h1>Modelos y derechos de visualización</h1>
    <p>La ficha, el procesamiento, la visualización y la descarga tienen estados independientes. Conceder derechos requiere evidencia documental.</p></div>
  <nav class="actions document-nav" aria-label="Centro documental">
    <a class="button button-ghost" routerLink="/admin/documentos">Documentos y estados</a>
    <a class="button button-ghost" routerLink="/admin/ifc">Inventario y permisos IFC</a>
  </nav>
  @if(error()){<p class="error" role="alert">{{error()}}</p>}
  <section class="panel">
    <div class="legacy-toolbar"><label>Soluciones<select [(ngModel)]="kind" (ngModelChange)="reset()"><option value="commercial">Comerciales</option><option value="generic">Genéricas</option></select></label>
      <label>Buscar por código o nombre<input type="search" [(ngModel)]="query" (keyup.enter)="search()"></label><button type="button" class="button button-ghost" (click)="search()">Buscar</button></div>
    <p class="small muted">{{total()}} IFC · página {{page()}} de {{pageCount()}} · {{selection().size}} seleccionados</p>
    <div class="actions"><button type="button" class="button button-ghost" (click)="selectPage()">Seleccionar página</button><button type="button" class="button button-ghost" (click)="selectFiltered()" [disabled]="busy()">Seleccionar filtrados (máximo 100)</button><button type="button" class="button button-ghost" (click)="clear()">Limpiar</button></div>
    <div class="technical-scroll legacy-table"><table><thead><tr><th>Seleccionar</th><th>Ficha</th><th>Tipo</th><th>Fabricante</th><th>IFC</th><th>Procesamiento</th><th>Integridad</th><th>Visualización</th><th>Descarga</th><th>Último cambio</th><th>Acción</th></tr></thead><tbody>
      @for(row of rows();track row.asset_id){<tr><td><input type="checkbox" [attr.aria-label]="'Seleccionar '+row.code" [checked]="selection().has(row.asset_id)" (change)="toggle(row)"></td>
        <td>{{row.code}}<br>{{row.name}}<br><small>{{row.solution_status}} @if(row.revision){· revisión {{row.revision}}}</small></td><td>{{row.kind==='generic'?'Genérica':'Comercial'}}</td><td>{{row.manufacturer||'—'}}</td><td>{{row.original_name}}</td><td>{{row.processing_status}}</td><td>{{row.integrity_status}}</td><td>{{row.public_view_allowed?'Autorizada':'Privada'}}</td><td>{{row.public_download_allowed?'Autorizada':'Privada'}}</td><td>{{row.last_permission_change_at?formatDate(row.last_permission_change_at):'Sin cambios'}}</td><td><button type="button" class="text-link" (click)="inspect(row)">Inspeccionar</button></td></tr>}
      @empty{<tr><td colspan="11">No hay IFC para este filtro.</td></tr>}
    </tbody></table></div><div class="actions"><button type="button" class="button button-ghost" [disabled]="page()<=1" (click)="go(page()-1)">Anterior</button><button type="button" class="button button-ghost" [disabled]="page()>=pageCount()" (click)="go(page()+1)">Siguiente</button></div>
  </section>
  @if(inspected();as row){<section class="panel"><h2>{{row.code}} · {{row.original_name}}</h2><p>SHA-256 registrado: <code>{{row.sha256}}</code></p>
    @if(integrity();as state){<p>Integridad: <strong>{{state.status}}</strong> · Extracción: {{state.extraction_valid?'Válida':'No válida o ausente'}} · Objetos con representación: {{state.representable_elements}}</p>}
    <div class="actions"><button type="button" class="button button-ghost" (click)="check(row)">Verificar integridad</button><button type="button" class="button button-ghost" (click)="processing(row)">Procesamiento</button><button type="button" class="button button-ghost" (click)="history(row)">Historial</button><button type="button" class="button button-ghost" (click)="reprocess(row)" [disabled]="busy()">Reprocesar</button>
      @if(row.processing_status==='VALID'){<button type="button" class="button button-ghost" (click)="viewer.set(row.asset_id)">Vista previa</button>}</div>
    @if(note()){<p class="notice" role="status">{{note()}}</p>}
    @if(historyRows().length){<h3>Historial de permisos</h3>@for(entry of historyRows();track entry.id){<p>{{entry.at}} · {{entry.detail.before}} → {{entry.detail.after}} · {{entry.detail.evidence||'Sin evidencia de nueva concesión'}}</p>}}
    @if(viewer()===row.asset_id){<app-viewer-host [assetId]="row.asset_id"/>}
  </section>}
  <section class="panel"><h2>Permisos del lote</h2><p>{{selection().size}} IFC seleccionados · {{validCount()}} válidos · {{selection().size-validCount()}} pendientes o inválidos · {{privateCount()}} sin visualización pública · {{viewCount()}} autorizados para visualizar · {{downloadCount()}} autorizados para descargar.</p>
    @if(selection().size){<p>Valores actuales: visualización <strong>{{mixed('public_view_allowed')}}</strong> · descarga <strong>{{mixed('public_download_allowed')}}</strong>.</p>
      <div class="technical-scroll legacy-preview"><ul>@for(row of selectedRows();track row.asset_id){<li>{{row.code}} · {{row.original_name}} · {{row.processing_status}} · integridad {{row.integrity_status}}</li>}</ul></div>}
    <div class="legacy-toolbar"><label>Visualización pública<select aria-label="Visualización pública propuesta" [(ngModel)]="viewIntent" (ngModelChange)="invalidateReview()"><option value="unchanged">Sin cambios</option><option value="allow">Activar</option><option value="deny">Desactivar</option></select></label>
      <label>Descarga pública<select aria-label="Descarga pública propuesta" [(ngModel)]="downloadIntent" (ngModelChange)="invalidateReview()"><option value="unchanged">Sin cambios</option><option value="allow">Activar</option><option value="deny">Desactivar</option></select></label></div>
    <label>Evidencia de autorización (obligatoria al conceder derechos)<textarea aria-label="Evidencia de autorización" [(ngModel)]="evidence" (ngModelChange)="invalidateReview()" maxlength="2000" rows="3"></textarea></label>
    <p class="small muted">La visualización actual transmite el IFC original al navegador. Concede derechos solo con autorización documental.</p>
    @if(reviewReason()){<p class="notice" role="status">{{reviewReason()}}</p>}
    @if(!review()){<button type="button" class="button" [disabled]="!!reviewReason()" (click)="openReview()">Revisar cambios</button>}
    @else {<div class="panel" role="dialog" aria-label="Revisión de permisos IFC"><h3>Revisar permisos antes de guardar</h3>
      <p>{{review()!.targets.length}} IFC afectados · {{review()!.viewOn}} activaciones y {{review()!.viewOff}} desactivaciones de visualización · {{review()!.downloadOn}} activaciones y {{review()!.downloadOff}} desactivaciones de descarga.</p>
      @if(review()!.excluded.length){<p>{{review()!.excluded.length}} excluidos: {{review()!.excluded.join('; ')}}</p>}
      @if(review()!.evidence){<p>Evidencia: {{review()!.evidence}}</p>}
      <p class="notice">Autorizar visualización puede permitir recuperar el IFC original recibido por el navegador.</p>
      <div class="actions"><button type="button" class="button" [disabled]="busy()" (click)="apply()">Confirmar y guardar</button><button type="button" class="button button-ghost" [disabled]="busy()" (click)="cancelReview()">Cancelar</button></div></div>}
    @if(busy()){<p role="status">Aplicando cambios…</p>}
    @if(results().length){<h3>Resultados</h3>@for(result of results();track result.asset_id){<p>{{result.asset_id}} · {{result.updated?'Guardado':(result.code||'ERROR')+' · '+result.message}}</p>}}
  </section>
</div>`})
export class AdminIfcComponent implements OnInit {
  private api=inject(ApiService);
  kind:'generic'|'commercial'='commercial';query='';private applied='';
  rows=signal<IfcRow[]>([]);page=signal(1);total=signal(0);selection=signal<Map<string,IfcRow>>(new Map());
  inspected=signal<IfcRow|null>(null);integrity=signal<Integrity|null>(null);historyRows=signal<History[]>([]);viewer=signal('');note=signal('');error=signal('');busy=signal(false);review=signal<Review|null>(null);results=signal<Change[]>([]);
  viewIntent:Intent='unchanged';downloadIntent:Intent='unchanged';evidence='';private run=0;
  ngOnInit(){void this.load()}
  formatDate(value:string){return new Date(value).toLocaleString('es-ES')}
  pageCount(){return Math.max(1,Math.ceil(this.total()/20))}
  params(page:number){return {kind:this.kind,q:this.applied,page,page_size:20}}
  async load(){const run=++this.run;try{const result=await this.api.page<IfcRow>('/admin/ifc/inventory',this.params(this.page()));if(run!==this.run)return;this.rows.set(result.data);this.total.set(result.meta?.total||0);const next=new Map(this.selection());for(const row of result.data)if(next.has(row.asset_id))next.set(row.asset_id,row);this.selection.set(next)}catch(e){if(run===this.run)this.error.set(problem(e))}}
  reset(){this.page.set(1);this.clear();this.inspected.set(null);void this.load()}
  search(){this.applied=this.query.trim();this.reset()}
  go(page:number){if(page<1||page>this.pageCount())return;this.page.set(page);void this.load()}
  clear(){this.selection.set(new Map());this.invalidateReview()}
  toggle(row:IfcRow){const next=new Map(this.selection());if(next.has(row.asset_id))next.delete(row.asset_id);else if(next.size<100)next.set(row.asset_id,row);else this.error.set('Máximo 100 IFC por lote');this.selection.set(next);this.invalidateReview()}
  selectPage(){const next=new Map(this.selection());for(const row of this.rows()){if(next.size>=100)break;next.set(row.asset_id,row)}this.selection.set(next);this.invalidateReview()}
  async selectFiltered(){if(this.busy())return;this.busy.set(true);try{const next=new Map(this.selection());for(let page=1;page<=Math.min(5,this.pageCount())&&next.size<100;page++){const result=await this.api.page<IfcRow>('/admin/ifc/inventory',this.params(page));for(const row of result.data){if(next.size>=100)break;next.set(row.asset_id,row)}}this.selection.set(next);this.invalidateReview()}catch(e){this.error.set(problem(e))}finally{this.busy.set(false)}}
  selectedRows(){return [...this.selection().values()]}
  validCount(){return this.selectedRows().filter(x=>x.processing_status==='VALID'&&x.integrity_status==='MATCH').length}
  privateCount(){return this.selectedRows().filter(x=>!x.public_view_allowed).length}
  viewCount(){return this.selectedRows().filter(x=>x.public_view_allowed).length}
  downloadCount(){return this.selectedRows().filter(x=>x.public_download_allowed).length}
  mixed(field:'public_view_allowed'|'public_download_allowed'){const rows=this.selectedRows();return rows.every(x=>x[field])?'Todas autorizadas':rows.every(x=>!x[field])?'Todas privadas':'Mixto'}
  proposed(row:IfcRow){return {public_view_allowed:this.viewIntent==='unchanged'?row.public_view_allowed:this.viewIntent==='allow',
    public_download_allowed:this.downloadIntent==='unchanged'?row.public_download_allowed:this.downloadIntent==='allow'}}
  plan():Review {const targets:Target[]=[],excluded:string[]=[];let viewOn=0,viewOff=0,downloadOn=0,downloadOff=0;
    for(const row of this.selectedRows()){const proposed=this.proposed(row),oldView=row.public_view_allowed,oldDownload=row.public_download_allowed;
      if(proposed.public_view_allowed===oldView&&proposed.public_download_allowed===oldDownload){excluded.push(row.code+' (sin cambios)');continue}
      if(((proposed.public_view_allowed&&!oldView)||(proposed.public_download_allowed&&!oldDownload))&&row.integrity_status!=='MATCH'){
        excluded.push(row.code+' (IFC ausente o con SHA-256 incorrecto)');continue}
      if(proposed.public_view_allowed&&!oldView&&row.processing_status!=='VALID'){excluded.push(row.code+' (procesamiento no válido)');continue}
      targets.push({kind:row.kind,target_id:row.target_id,asset_id:row.asset_id,
        expected:{public_view_allowed:oldView,public_download_allowed:oldDownload},
        policy:{...proposed,rights_evidence:this.evidence.trim()}});
      if(proposed.public_view_allowed&&!oldView)viewOn++;if(!proposed.public_view_allowed&&oldView)viewOff++;
      if(proposed.public_download_allowed&&!oldDownload)downloadOn++;if(!proposed.public_download_allowed&&oldDownload)downloadOff++;
    }return {targets,excluded,viewOn,viewOff,downloadOn,downloadOff,evidence:this.evidence.trim()}}
  reviewReason(){if(this.busy())return 'Hay una operación en curso';if(!this.selection().size)return 'Selecciona al menos un IFC';
    const draft=this.plan();if(!draft.targets.length)return draft.excluded.some(x=>!x.includes('sin cambios'))?'Los documentos seleccionados no son elegibles':'No has modificado ningún permiso';
    if((draft.viewOn+draft.downloadOn)>0&&draft.evidence.length<10)return 'Introduce al menos 10 caracteres de evidencia de autorización';return ''}
  invalidateReview(){this.review.set(null)}
  openReview(){if(this.reviewReason())return;this.review.set(this.plan());this.results.set([])}
  cancelReview(){this.review.set(null)}
  inspect(row:IfcRow){this.inspected.set(row);this.integrity.set(null);this.historyRows.set([]);this.viewer.set('');this.note.set('');void this.check(row)}
  async check(row:IfcRow){try{this.integrity.set(await this.api.get<Integrity>('/admin/ifc/'+row.asset_id+'/integrity'))}catch(e){this.error.set(problem(e))}}
  async processing(row:IfcRow){try{const state=await this.api.get<{state:string;warnings:string[]}>('/documents/'+row.asset_id+'/processing');this.note.set([state.state,...state.warnings].join(' · '))}catch(e){this.error.set(problem(e))}}
  async history(row:IfcRow){try{this.historyRows.set(await this.api.list<History>('/admin/ifc/'+row.asset_id+'/history'))}catch(e){this.error.set(problem(e))}}
  async reprocess(row:IfcRow){this.busy.set(true);try{await this.api.post('/admin/assets/'+row.asset_id+'/reprocess',{});await this.load();this.note.set('IFC puesto en cola para reprocesamiento')}catch(e){this.error.set(problem(e))}finally{this.busy.set(false)}}
  async apply(){const reviewed=this.review();if(this.busy()||!reviewed?.targets.length)return;this.busy.set(true);this.error.set('');try{
      const result=await this.api.post<Change[]>('/admin/ifc/permissions/bulk',{confirmed:true,targets:reviewed.targets});this.results.set(result);
      const next=new Map(this.selection());for(const item of result)if(item.updated)next.delete(item.asset_id);this.selection.set(next);this.review.set(null);
      await this.load();if(result.some(x=>!x.updated))this.error.set('Algunos IFC no se actualizaron. Revisa los resultados y vuelve a cargar sus permisos.');
    }catch(e){this.error.set(problem(e));this.review.set(null)}finally{this.busy.set(false)}}
}
