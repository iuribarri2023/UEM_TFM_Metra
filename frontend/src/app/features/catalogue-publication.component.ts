import {Component,inject,OnInit,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {ApiService,Asset,Generic,Product,problem} from '../core/api';
import {DocumentPolicy,DocumentPolicyComponent} from './document-policy.component';
import {ViewerHostComponent} from './viewer-host.component';

interface Row {id:string;code:string;name:string;kind:string;manufacturer:string|null;classification:string;status:string;revision:number|null;updated_at:string;ifc_status:string;has_bc3:boolean;has_epd:boolean;warnings:string[];ifc_count:number;ifc_valid:number;ifc_invalid:number;ifc_missing_file:number;ifc_private:number;ifc_view_allowed:number;ifc_download_allowed:number}
interface Publication {id:string;published:boolean;message?:string;code?:string;details?:string[]}

@Component({standalone:true,imports:[FormsModule,DocumentPolicyComponent,ViewerHostComponent],template:`
<div class="container content portal-content">
  <div class="portal-page-title"><span class="eyebrow">ADMINISTRACIÓN / CATÁLOGO METRA-DEMO</span><h1>Publicación del inventario</h1>
    <p>Publicación editorial del catálogo. La validez técnica y las autorizaciones de documentos se gestionan por separado.</p></div>
  @if(error()){<p class="error" role="alert">{{error()}}</p>}
  <section class="panel">
    <div class="legacy-toolbar">
      <label>Tipo<select [(ngModel)]="kind" (ngModelChange)="resetAndLoad()" [disabled]="busy()"><option value="commercial">Productos comerciales</option><option value="generic">Referencias genéricas</option></select></label>
      <label>Estado<select [(ngModel)]="status" (ngModelChange)="resetAndLoad()" [disabled]="busy()"><option value="pending">Pendientes</option><option value="published">Publicadas</option><option value="all">Todas</option></select></label>
      <label>Buscar<input type="search" [(ngModel)]="query" (keyup.enter)="search()" placeholder="Código, nombre o fabricante"></label>
      <button type="button" class="button button-ghost" (click)="search()">Buscar</button>
      <label>Orden<select [(ngModel)]="sort" (ngModelChange)="resetAndLoad()"><option value="code">Código</option><option value="name">Nombre</option><option value="updated">Actualización</option></select></label>
    </div>
    <p class="small muted">{{total()}} fichas en el filtro · {{selection().size}} seleccionadas · página {{page()}} de {{pageCount()}}</p>
    <div class="actions">
      <button type="button" class="button button-ghost" (click)="selectPage()" [disabled]="busy()">Seleccionar página</button>
      <button type="button" class="button button-ghost" (click)="selectFiltered()" [disabled]="busy()">Seleccionar filtradas (máximo 100)</button>
      <button type="button" class="button button-ghost" (click)="clearSelection()" [disabled]="busy()">Limpiar selección</button>
    </div>
    <div class="technical-scroll legacy-table"><table><thead><tr><th>Selección</th><th>Código / nombre</th><th>Tipo</th><th>Fabricante</th><th>Clasificación</th><th>Estado</th><th>Revisión</th><th>IFC</th><th>BC3</th><th>EPD</th><th>Advertencias</th><th>Actualización</th></tr></thead><tbody>
      @for(row of rows();track row.id){<tr><td><input type="checkbox" [attr.aria-label]="'Seleccionar '+row.name" [checked]="selection().has(row.id)" (change)="toggle(row)"></td>
        <td><button type="button" class="text-link" (click)="inspect(row)">{{row.code}}</button><br>{{row.name}}</td><td>{{row.kind==='generic'?'Genérica':'Comercial'}}</td><td>{{row.manufacturer||'—'}}</td><td>{{row.classification}}</td><td>{{row.status}}</td><td>{{row.revision||'—'}}</td><td>{{row.ifc_status}}</td><td>{{row.has_bc3?'Sí':'No'}}</td><td>{{row.has_epd?'Sí':'No'}}</td><td>{{row.warnings.join(' · ')||'—'}}</td><td>{{row.updated_at.slice(0,10)}}</td></tr>}
      @empty{<tr><td colspan="12">No hay fichas para este filtro.</td></tr>}
    </tbody></table></div>
    <div class="actions"><button type="button" class="button button-ghost" (click)="go(page()-1)" [disabled]="page()<=1||busy()">Anterior</button><button type="button" class="button button-ghost" (click)="go(page()+1)" [disabled]="page()>=pageCount()||busy()">Siguiente</button></div>
  </section>
  @if(selected();as item){<section class="panel legacy-detail"><h2>{{item.name}}</h2><p>{{item.code}}</p>
    @for(asset of assets();track asset.id){<app-document-policy [asset]="asset" (policy)="setPolicy(item.id,asset.id,$event)"/>
      <div class="file-row"><span>{{asset.original_name}} · {{asset.processing_status}}</span><button type="button" class="text-link" (click)="download(asset)">Descargar original</button>
      <button type="button" class="text-link" (click)="reprocess(asset)">Reprocesar</button>
      @if(asset.file_type==='IFC'&&asset.processing_status==='VALID'){<button type="button" class="text-link" (click)="viewer.set(asset.id)">Ver IFC</button>}</div>}
    @if(viewer()){<app-viewer-host [assetId]="viewer()"/>}
  </section>}
  <section class="panel"><h2>Revisar publicación</h2><p>{{selection().size}} fichas seleccionadas.</p>
    <p class="small">IFC vinculados: {{sum('ifc_count')}} · válidos: {{sum('ifc_valid')}} · inválidos: {{sum('ifc_invalid')}} · sin archivo: {{sum('ifc_missing_file')}} · privados: {{sum('ifc_private')}} · visualización autorizada: {{sum('ifc_view_allowed')}} · descarga autorizada: {{sum('ifc_download_allowed')}}.</p>
    <p class="small"><a href="/admin/ifc">Gestionar IFC y sus permisos</a> antes de confirmar este lote.</p>
    @if(selection().size){<div class="technical-scroll legacy-preview"><ul>@for(row of selectedRows();track row.id){<li>{{row.code}} · {{row.name}}</li>}</ul></div>}
    <label>Evidencia de autorización editorial<textarea [(ngModel)]="evidence" maxlength="2000" rows="3"></textarea></label>
    <label class="inline-check"><input type="checkbox" [(ngModel)]="confirmed"> Confirmo que la evidencia cubre las fichas seleccionadas</label>
    @if(!reviewing()){
      <p><button type="button" class="button" [disabled]="busy()||!selection().size||!confirmed||evidence.trim().length<10" (click)="review()">Revisar fichas seleccionadas</button></p>
    }@else{
      <p class="notice">Confirma la publicación de {{selection().size}} fichas. Los documentos conservarán acceso privado salvo autorizaciones específicas registradas en su detalle.</p>
      <div class="actions"><button type="button" class="button" [disabled]="busy()" (click)="publish()">Confirmar y publicar</button><button type="button" class="button button-ghost" [disabled]="busy()" (click)="reviewing.set(false)">Cancelar</button></div>
    }
    @if(busy()){<p role="status">Publicando lote… {{progress()}}</p>}
    @if(results().length){<h3>Resultado del lote</h3>@for(result of results();track result.id){<div class="file-row"><span>{{result.name}}</span><strong>{{result.published?'Publicada':result.message||'Error'}}</strong></div>}}
  </section>
</div>`})
export class AdminLegacyComponent implements OnInit {
  private api=inject(ApiService);
  kind:'commercial'|'generic'='commercial';status:'pending'|'published'|'all'='pending';sort:'code'|'name'|'updated'='code';query='';private appliedQuery='';
  rows=signal<Row[]>([]);page=signal(1);total=signal(0);selection=signal<Map<string,Row>>(new Map());
  selected=signal<Row|null>(null);assets=signal<Asset[]>([]);viewer=signal('');error=signal('');busy=signal(false);reviewing=signal(false);progress=signal('');
  results=signal<(Publication&{name:string})[]>([]);evidence='';confirmed=false;policies:Record<string,Record<string,DocumentPolicy>>={};
  private requestNumber=0;
  async ngOnInit(){await this.load()}
  pageCount(){return Math.max(1,Math.ceil(this.total()/20))}
  private params(page:number){return {kind:this.kind,status:this.status,sort:this.sort,q:this.appliedQuery,page,page_size:20}}
  async load(){const request=++this.requestNumber;this.error.set('');try{const r=await this.api.page<Row>('/admin/legacy/inventory',this.params(this.page()));if(request===this.requestNumber){this.rows.set(r.data);this.total.set(r.meta?.total||0)}}catch(e){if(request===this.requestNumber)this.error.set(problem(e))}}
  resetAndLoad(){this.page.set(1);this.clearSelection();this.selected.set(null);this.assets.set([]);void this.load()}
  search(){this.appliedQuery=this.query.trim();this.resetAndLoad()}
  go(page:number){if(page<1||page>this.pageCount())return;this.page.set(page);void this.load()}
  selectedRows(){return [...this.selection().values()]}
  sum(key:'ifc_count'|'ifc_valid'|'ifc_invalid'|'ifc_missing_file'|'ifc_private'|'ifc_view_allowed'|'ifc_download_allowed'){return this.selectedRows().reduce((n,row)=>n+(row[key]||0),0)}
  toggle(row:Row){const next=new Map(this.selection());if(next.has(row.id))next.delete(row.id);else if(next.size<100)next.set(row.id,row);else this.error.set('Máximo 100 fichas por lote');this.selection.set(next);this.reviewing.set(false)}
  selectPage(){const next=new Map(this.selection());for(const row of this.rows()){if(next.size>=100)break;next.set(row.id,row)}this.selection.set(next);this.reviewing.set(false)}
  async selectFiltered(){if(this.busy())return;this.busy.set(true);this.error.set('');try{const next=new Map(this.selection());const pages=Math.min(5,Math.ceil(this.total()/20));for(let p=1;p<=pages&&next.size<100;p++){const r=await this.api.page<Row>('/admin/legacy/inventory',this.params(p));for(const row of r.data){if(next.size>=100)break;next.set(row.id,row)}}this.selection.set(next);this.reviewing.set(false)}catch(e){this.error.set(problem(e))}finally{this.busy.set(false)}}
  clearSelection(){this.selection.set(new Map());this.reviewing.set(false)}
  async inspect(row:Row){this.selected.set(row);this.assets.set([]);this.viewer.set('');try{const detail=row.kind==='commercial'?await this.api.get<Product>('/admin/legacy/products/'+row.id):await this.api.get<Generic>('/admin/catalogue/generic-solutions/'+row.id);if(this.selected()?.id!==row.id)return;this.assets.set(row.kind==='commercial'?(detail as Product).revisions?.[0]?.assets||[]:(detail as Generic).assets||[])}catch(e){this.error.set(problem(e))}}
  setPolicy(target:string,asset:string,policy:DocumentPolicy|null){const next=this.policies[target]||={};if(policy)next[asset]=policy;else delete next[asset]}
  async download(asset:Asset){try{await this.api.download('/assets/'+asset.id+'/download',asset.original_name)}catch(e){this.error.set(problem(e))}}
  async reprocess(asset:Asset){try{const state=await this.api.post<{processing_status:string}>('/admin/assets/'+asset.id+'/reprocess',{});this.assets.update(xs=>xs.map(x=>x.id===asset.id?{...x,...state}:x));this.viewer.set('')}catch(e){this.error.set(problem(e))}}
  review(){if(!this.busy()&&this.selection().size&&this.confirmed&&this.evidence.trim().length>=10)this.reviewing.set(true)}
  async publish(){if(this.busy()||!this.reviewing()||!this.selection().size||!this.confirmed||this.evidence.trim().length<10)return;
    this.busy.set(true);this.error.set('');const selected=this.selectedRows();const ids=selected.map(x=>x.id);this.progress.set(`0 / ${ids.length}`);
    try{const outcome=await this.api.post<Publication[]>('/admin/legacy/publications',{kind:this.kind,ids,evidence:this.evidence.trim(),confirmed:true,document_permissions:this.policies});
      const names=new Map(selected.map(x=>[x.id,x.name]));this.results.set(outcome.map(x=>({...x,name:names.get(x.id)||x.id})));
      const next=new Map(this.selection());for(const x of outcome){if(x.published)next.delete(x.id)}this.selection.set(next);
      this.progress.set(`${outcome.filter(x=>x.published).length} / ${ids.length}`);this.reviewing.set(false);this.confirmed=false;await this.load();
    }catch(e){this.error.set(problem(e));this.reviewing.set(false)}finally{this.busy.set(false)}}
}
