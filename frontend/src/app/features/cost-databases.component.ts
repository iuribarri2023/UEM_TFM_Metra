import {Component,inject,OnInit,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {ApiService,problem} from '../core/api';

interface CostDatabase{id:string;name:string;sha256:string|null;version_id:string|null;created_at:string}
interface ImportJob{asset_id:string;id:string;name:string;original_name:string;state:string;progress:number;version_id?:string;concept_count?:number;error_code?:string}
interface Concept{code:string;description:string;unit:string;unit_price:number|null;children:{code:string;factor:number|null;quantity:number|null}[]}

@Component({standalone:true,imports:[FormsModule],template:`
<div class="container content portal-content">
  <div class="portal-page-title"><span class="eyebrow">ADMINISTRACIÓN / ECONOMÍA</span><h1>Bases de costes</h1>
    <p>Importa y consulta bases de referencia FIEBDC-3 y sus versiones.</p>
  </div>
  @if(error()){<p class="error" role="alert">{{error()}}</p>}
  <div class="portal-two-col">
    <section class="panel">
      <form (ngSubmit)="importBook()">
        <label>Nombre de base<input name="name" [(ngModel)]="name" required maxlength="180"></label>
        <label>Archivo BC3 o ZIP<input #fileControl type="file" accept=".bc3,.zip" required (change)="file=fileControl.files?.[0]"></label>
        <button class="button" [disabled]="busy()||!name.trim()||!file">Importar versión</button>
      </form>
      <div class="actions"><h2>Importaciones</h2><button class="button button-ghost" (click)="refresh()">Actualizar estado</button></div>
      @if(importMessage()){<p role="status">{{importMessage()}}</p>}
      @for(job of jobs();track job.asset_id){
        <div class="file-row">
          <div><strong>{{job.name}}</strong><p class="small muted">{{job.original_name}} · {{job.state}} · {{job.progress}} %</p></div>
          @if(job.version_id){<span>{{job.concept_count}} conceptos</span>}
          @if(job.error_code){<span>{{job.error_code}}</span>}
          @if(job.state==='INVALID'||job.state==='CANCELLED'){<button class="text-link" (click)="retry(job)">Reintentar</button>}
          @if(job.state==='PENDING'){<button class="text-link" (click)="cancel(job)">Cancelar</button>}
        </div>
      }
      <h2>Bases de referencia</h2>
      @for(v of versions();track v.id){
        <button class="legacy-item" [class.selected]="selected()?.id===v.id" (click)="choose(v)"><strong>{{v.name}}</strong><small>{{v.created_at.slice(0,10)}} · {{v.sha256?.slice(0,12)}}</small></button>
      }@empty{<p class="muted">Sin bases importadas.</p>}
    </section>
    <section class="panel">
      @if(selected();as v){
        <h2>{{v.name}}</h2>
        @if(v.version_id){
          <button class="button button-ghost" (click)="exportBook(v)">Descargar BC3 regenerado</button>
          <button class="button button-ghost" (click)="downloadSource(v)">Original</button>
        }
        @if(v.version_id){<form (ngSubmit)="loadConcepts(1)" class="catalog-search"><label class="sr-only" for="concept">Buscar conceptos</label>
          <input id="concept" name="concept" [(ngModel)]="query" placeholder="Código o descripción">
          <button class="button">Buscar</button></form>
        <p>{{total()}} conceptos · Página {{page()}}</p>
        <div class="technical-scroll">
          @for(c of concepts();track c.code){
            <details class="component" (toggle)="inspect(c,$event)"><summary>{{c.code}} · {{c.description}} · {{c.unit_price ?? '—'}} {{c.unit}}</summary>
              <form class="form-grid" (ngSubmit)="save(c)">
                <label>Descripción<input name="description" [(ngModel)]="c.description" required></label>
                <label>Unidad<input name="unit" [(ngModel)]="c.unit"></label>
                <label>Precio<input name="price" type="number" step="any" [(ngModel)]="c.unit_price" required></label>
                <button class="button button-ghost">Guardar concepto</button>
              </form>
              @for(child of children()[c.code]||[];track $index){<p>{{child.code}} · Factor {{child.factor ?? '—'}} · Rendimiento {{child.quantity ?? '—'}}</p>}
            </details>
          }
        </div>
        <button class="button button-ghost" [disabled]="page()<=1" (click)="loadConcepts(page()-1)">Anterior</button>
        <button class="button button-ghost" [disabled]="page()*50>=total()" (click)="loadConcepts(page()+1)">Siguiente</button>}@else{<p class="muted">Esta base todavía no tiene una versión procesada.</p>}
      }@else{<p class="muted">Selecciona una versión para explorar sus conceptos.</p>}
    </section>
  </div>
</div>`})
export class CostDatabasesComponent implements OnInit{
  private api=inject(ApiService);
  versions=signal<CostDatabase[]>([]);selected=signal<CostDatabase|null>(null);
  concepts=signal<Concept[]>([]);page=signal(1);total=signal(0);error=signal('');busy=signal(false);
  children=signal<Record<string,Concept['children']>>({});
  jobs=signal<ImportJob[]>([]);importMessage=signal('');
  name='';query='';file?:File;
  private loadNumber=0;
  async ngOnInit(){await this.refresh()}
  async refresh(){
    const selected=this.selected()?.id;
    const results=await Promise.allSettled([
      this.api.listAll<CostDatabase>('/cost-databases').then(rows=>{
        this.versions.set(rows);
        const latest=rows.find(row=>row.id===selected);
        if(latest&&this.selected()?.version_id!==latest.version_id)void this.choose(latest);
      }),
      this.api.list<ImportJob>('/cost-databases/imports',{page_size:20}).then(rows=>this.jobs.set(rows))
    ]);
    const failure=results.find(result=>result.status==='rejected');
    if(failure?.status==='rejected')this.error.set(problem(failure.reason));
  }
  async importBook(){
    if(!this.file||this.busy())return;
    this.busy.set(true);this.error.set('');
    try{
      await this.api.upload('/cost-databases/imports',this.file,{name:this.name.trim()});
      this.importMessage.set('Original recibido. Actualiza el estado para comprobar el resultado.');
      this.file=undefined;
      await this.refresh();
    }catch(e){this.error.set(problem(e))}
    finally{this.busy.set(false)}
  }
  async retry(job:ImportJob){await this.jobAction(job,'retry')}
  async cancel(job:ImportJob){await this.jobAction(job,'cancel')}
  private async jobAction(job:ImportJob,action:'retry'|'cancel'){
    try{await this.api.post('/documents/'+job.asset_id+'/'+action,{});await this.refresh()}
    catch(e){this.error.set(problem(e))}
  }
  async choose(version:CostDatabase){this.selected.set(version);this.query='';this.concepts.set([]);this.children.set({});if(version.version_id)await this.loadConcepts(1)}
  async loadConcepts(page:number){
    const item=this.selected();
    if(!item)return;
    const run=++this.loadNumber;
    try{
      const result=await this.api.page<Concept>('/cost-databases/'+item.id+'/concepts',{q:this.query,page,page_size:50});
      if(run!==this.loadNumber)return;
      this.concepts.set(result.data);this.total.set(result.meta?.total||0);this.page.set(page);
    }catch(e){if(run===this.loadNumber)this.error.set(problem(e))}
  }
  async inspect(concept:Concept,event:Event){
    const item=this.selected();
    if(!item||!(event.target as HTMLDetailsElement).open||this.children()[concept.code])return;
    try{
      const rows=await this.api.get<Concept['children']>('/cost-databases/'+item.id+'/concepts/'+encodeURIComponent(concept.code)+'/decomposition');
      if(this.selected()?.id===item.id)this.children.update(value=>({...value,[concept.code]:rows}));
    }catch(e){this.error.set(problem(e))}
  }
  async save(concept:Concept){
    const item=this.selected();
    if(!item)return;
    try{await this.api.patch('/cost-databases/'+item.id+'/concepts/'+encodeURIComponent(concept.code),
      {description:concept.description,unit:concept.unit,unit_price:concept.unit_price});await this.loadConcepts(this.page())}
    catch(e){this.error.set(problem(e))}
  }
  async downloadSource(item:CostDatabase){
    try{await this.api.download('/cost-databases/'+item.id+'/source-file',item.name+'-original')}
    catch(e){this.error.set(problem(e))}
  }
  async exportBook(item:CostDatabase){
    try{await this.api.download('/cost-databases/'+item.id+'/export/bc3',item.name+'.bc3')}
    catch(e){this.error.set(problem(e))}
  }
}
