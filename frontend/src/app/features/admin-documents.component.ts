import {Component,inject,signal} from '@angular/core';
import {RouterLink} from '@angular/router';
import {FormsModule} from '@angular/forms';
import {ApiService,Asset,problem} from '../core/api';
import {DocumentPolicy,DocumentPolicyComponent} from './document-policy.component';
import {ViewerHostComponent} from './viewer-host.component';

interface Target{id:string;code:string;name_es:string;assets:Asset[];status?:string}

@Component({standalone:true,imports:[FormsModule,RouterLink,DocumentPolicyComponent,ViewerHostComponent],template:`
<div class="container content portal-content">
  <span class="eyebrow">ADMINISTRACIÓN / DOCUMENTOS</span><h1>Documentos y permisos</h1>
  <p>La visualización y la descarga son permisos independientes. Los cambios quedan registrados.</p>
  <nav class="actions document-nav" aria-label="Centro documental">
    <a class="button button-ghost" routerLink="/admin/documentos">Documentos y estados</a>
    <a class="button button-ghost" routerLink="/admin/ifc">Inventario y permisos IFC</a>
  </nav>
  <form class="catalog-controls" (ngSubmit)="load()">
    <label>Soluciones<select name="kind" [(ngModel)]="kind" (ngModelChange)="load()">
      <option value="commercial">Comerciales publicadas</option><option value="generic">Genéricas</option>
    </select></label>
    <label>Nombre o código<input type="search" name="q" [(ngModel)]="query"></label>
    <button class="button">Buscar</button>
  </form>
  @if(error()){<p role="alert" class="error">{{error()}}</p>}
  @if(message()){<p role="status" class="notice">{{message()}}</p>}
  <div class="portal-two-col">
    <section class="panel">
      @for(row of items();track row.id){
        <button class="legacy-item" [class.selected]="selected()?.id===row.id" (click)="choose(row)">{{row.code}} · {{row.name_es}}</button>
      }@empty{<p class="muted">Sin resultados.</p>}
    </section>
    <section class="panel">
      @if(selected();as row){
        <h2>{{row.name_es}}</h2>
        @if(kind==='generic'&&row.status==='DRAFT'){
          <label>Asociar un documento al borrador<input #uploadControl type="file" accept=".ifc,.bc3,.zip,.xml" (change)="upload(uploadControl)"></label>
        }
        @for(asset of row.assets;track asset.id){
          <app-document-policy [asset]="asset" (policy)="setPolicy(asset.id,$event)"/>
          <div class="actions">
            <button class="button" [disabled]="!policies()[asset.id]||busy()" (click)="save(row,asset)">Guardar permisos</button>
            <button class="button button-ghost" (click)="download(asset)">Original</button>
            <button class="button button-ghost" (click)="check(asset)">Estado y advertencias</button>
            @if(asset.file_type==='IFC'&&asset.processing_status==='VALID'){
              <button class="button button-ghost" (click)="viewer.set(asset.id)">Vista previa IFC</button>
            }
            <button class="button button-ghost" (click)="reprocess(asset)">Reprocesar</button>
          </div>
        }@empty{<p class="muted">Sin documentos asociados.</p>}
        @for(id of viewer()?[viewer()]:[];track id){<app-viewer-host [assetId]="id"/>}
      }
    </section>
  </div>
</div>`})
export class AdminDocumentsComponent {
  private api=inject(ApiService);
  kind='commercial';query='';
  items=signal<Target[]>([]);selected=signal<Target|null>(null);
  error=signal('');message=signal('');viewer=signal('');busy=signal(false);
  policies=signal<Record<string,DocumentPolicy>>({});
  private run=0;
  async ngOnInit(){await this.load()}
  choose(row:Target){this.selected.set(row);this.policies.set({});this.viewer.set('');this.message.set('')}
  setPolicy(id:string,value:DocumentPolicy|null){
    this.policies.update(previous=>{const next={...previous};if(value)next[id]=value;else delete next[id];return next});
  }
  async load(keep?:string){
    const run=++this.run;
    this.error.set('');
    if(!keep){this.chooseEmpty();this.items.set([])}
    try{
      const rows=await this.api.listAll<Target>('/admin/document-targets',{kind:this.kind,q:this.query});
      if(run!==this.run)return;
      this.items.set(rows);
      const row=rows.find(item=>item.id===keep);
      if(row)this.choose(row);
    }catch(e){if(run===this.run)this.error.set(problem(e))}
  }
  private chooseEmpty(){this.selected.set(null);this.policies.set({});this.viewer.set('');this.message.set('')}
  async save(row:Target,asset:Asset){
    this.busy.set(true);this.error.set('');
    const entity=this.kind==='generic'?'generic-solutions':'products';
    try{
      await this.api.patch('/admin/'+entity+'/'+row.id+'/assets/'+asset.id,this.policies()[asset.id]);
      await this.load(row.id);this.message.set('Permisos guardados y auditados.');
    }catch(e){this.error.set(problem(e))}
    finally{this.busy.set(false)}
  }
  async upload(input:HTMLInputElement){
    const row=this.selected(),file=input.files?.[0];
    if(!row||!file)return;
    try{await this.api.upload('/admin/generic-solutions/'+row.id+'/assets',file);await this.load(row.id);
      this.message.set('Original guardado. Procesamiento en cola.');input.value=''}
    catch(e){this.error.set(problem(e))}
  }
  async download(asset:Asset){try{await this.api.download('/documents/'+asset.id+'/download',asset.original_name)}catch(e){this.error.set(problem(e))}}
  async check(asset:Asset){
    try{
      const status=await this.api.get<{state:string;progress:number;warnings:string[]}>('/documents/'+asset.id+'/processing');
      const id=this.selected()?.id;
      if(id&&status.state!==asset.processing_status)await this.load(id);
      this.message.set([status.state,status.progress+' %',...status.warnings].join(' · '));
    }catch(e){this.error.set(problem(e))}
  }
  async reprocess(asset:Asset){
    try{await this.api.post('/admin/assets/'+asset.id+'/reprocess',{});await this.check(asset)}
    catch(e){this.error.set(problem(e))}
  }
}
