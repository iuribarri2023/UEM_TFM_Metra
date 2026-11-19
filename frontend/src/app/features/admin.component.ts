import {DocumentPolicy,DocumentPolicyComponent} from './document-policy.component';
import {Component,inject,OnInit,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {RouterLink,ActivatedRoute} from '@angular/router';
import {ApiService,SessionService,Revision,Taxon,AuditEntry,problem} from '../core/api';
import {TechnicalPanelsComponent} from './technical-panels.component';
import {SolutionSection,SolutionShellComponent} from './solution-shell.component';
@Component({standalone:true,imports:[FormsModule,RouterLink,SolutionShellComponent,TechnicalPanelsComponent,DocumentPolicyComponent],template:`<div class="container content"><span class="eyebrow">Gobierno del catálogo</span><h1>{{tab()==='reviews'?'Revisión de productos':tab()==='catalogue'?'Taxonomía y genéricas':'Auditoría'}}</h1>
@if(session.role()!=='ADMIN'){<p class="notice">Se requieren permisos de administración. <a routerLink="/acceso">Identificarse</a></p>}@else{
@if(error()){<p class="error">{{error()}}</p>}@if(info()){<p class="notice">{{info()}}</p>}
@if(tab()==='reviews'){<div class="detail-grid review-workspace"><section class="panel"><h2>Cola de revisión <span class="tag">{{queue().length}}</span></h2>
<label>Filtrar revisiones<input type="search" [(ngModel)]="filter" placeholder="Nombre del producto"></label>
<div class="actions">
  <button class="button button-ghost" [disabled]="!filtered().length" (click)="selectVisible()">Seleccionar visibles</button>
  <button class="text-link" [disabled]="!batch().length" (click)="batch.set([])">Limpiar selección</button>
</div>
<div class="technical-scroll">
  <table class="work-table"><thead><tr><th scope="col">Lote</th><th scope="col">Producto</th><th scope="col">IFC válido</th></tr></thead>
    <tbody>@for(r of filtered();track r.id){
      <tr><td><input type="checkbox" [attr.aria-label]="'Seleccionar '+r.name_es" [checked]="batch().includes(r.id)" (change)="toggle(r.id)"></td>
        <td><button class="text-link" (click)="inspect(r.id)">{{r.name_es}}</button><br><small>Revisión #{{r.number}}</small></td>
        <td>{{ifcCount(r)}}</td></tr>
    }@empty{<tr><td colspan="3">Sin revisiones pendientes en esta selección.</td></tr>}</tbody>
  </table>
</div>
@if(batch().length){
  <h3>Vista previa · {{batch().length}} revisiones</h3>
  <ul>@for(r of batchItems();track r.id){<li>{{r.name_es}} · #{{r.number}}</li>}</ul>
  <label class="format-filter"><input type="checkbox" [(ngModel)]="confirmed"> Confirmo la aprobación editorial del lote</label>
  <button class="button" [disabled]="!confirmed||busy()" (click)="approveBatch()">Aprobar lote</button>
}
@for(result of batchResults();track result.id){<div class="file-row"><span>{{result.name}}</span><strong>{{result.published?'Publicada':result.message}}</strong></div>}
</section><section class="panel">
@if(inspecting()){<p role="status">Cargando revisión…</p>}
@if(selected();as r){
  <span class="tag">PENDIENTE</span><h2>{{r.name_es}}</h2><p>{{r.description}}</p><p>Unidad funcional · {{r.functional_unit}}</p>
  <app-solution-shell [assets]="r.assets" [bimStatus]="r.bim_status" [revisionId]="r.id" [review]="true"
    [section]="reviewSection()" (sectionChange)="reviewSection.set($event)">
    @if(reviewSection()==='Visión general'){
      <h3>Resumen de revisión</h3><p>{{r.description||'Sin descripción declarada.'}}</p>
      <p>{{r.assets.length}} documentos · {{ifcCount(r)}} IFC válidos</p>
    }@else if(reviewSection()==='Historial'){
      <h3>Revisión #{{r.number}}</h3><p>{{r.status}} @if(r.created_at){· {{r.created_at.slice(0,10)}}}</p>
    }@else{
      <app-technical-panels [section]="reviewSection()" [technical]="r.technical_data" [economic]="r.economic_data"
        [environmental]="r.environmental_data" [composition]="r.technical_data?.composition||[]" [assets]="r.assets"/>
    }
  </app-solution-shell>
  @for(a of r.assets;track a.id){<app-document-policy [asset]="a" (policy)="setPolicy(r.id,a.id,$event)"/><div class="file-row"><strong>{{a.file_type}} · {{a.original_name}}</strong><span>{{a.processing_status}}</span>
    <button class="text-link" (click)="download(a.id,a.original_name)">Descargar</button></div>
  }
  <h3>Comprobaciones para decidir</h3>
  <ul class="editor-checklist">
    <li>{{ifcCount(r)}} IFC procesados como válidos</li>
    <li>{{r.assets.length}} documentos vinculados</li>
    <li>{{r.functional_unit?'Unidad funcional declarada':'Sin unidad funcional declarada'}}</li>
  </ul>
  <h3>Decisión administrativa</h3><label>Motivo<textarea [(ngModel)]="reason" maxlength="2000" placeholder="Explica la decisión"></textarea></label>
  <div class="actions"><button class="button" [disabled]="busy()" (click)="decide('approve')">Aprobar y publicar</button>
  <button class="button button-ghost" [disabled]="busy()||reason.trim().length<5" (click)="decide('corrections')">Solicitar correcciones</button>
  <button class="button danger" [disabled]="busy()||reason.trim().length<5" (click)="decide('reject')">Rechazar</button></div>
}@else{<p class="muted">Selecciona una revisión para comprobarla.</p>}
</section></div>}
@if(tab()==='catalogue'){
<section class="panel">
  <h2>Entidades del catálogo</h2>
  <div class="work-controls">
    <label>Entidad<select [(ngModel)]="kind" (ngModelChange)="loadCatalogue()">
      <option value="systems">Sistemas</option><option value="subsystems">Subsistemas</option>
      <option value="archetypes">Arquetipos</option><option value="generic-solutions">Soluciones genéricas</option>
      <option value="slots">Componentes de genéricas</option>
    </select></label>
    <label>Buscar<input type="search" [(ngModel)]="catalogueSearch" placeholder="Nombre o código"></label>
    <button class="button" (click)="beginCreate()">Nuevo registro</button>
  </div>
  @if(catalogueLoading()){<p role="status">Cargando registros…</p>}
  @else{
    <div class="technical-scroll"><table class="work-table"><thead><tr>
      <th scope="col">Nombre</th><th scope="col">Código</th><th scope="col">Estado</th><th scope="col">Acciones</th>
    </tr></thead><tbody>@for(x of visibleEntries();track x.id){
      <tr><td>{{x.name_es}}</td><td>{{x.code}}</td><td>{{x.status||(x.archived?'Archivado':'Activo')}}</td>
        <td><div class="actions">
          @if(kind!=='generic-solutions'||x.status==='DRAFT'){<button class="text-link" (click)="beginEdit(x)">Editar</button>}
          <button class="text-link" (click)="pending={record:x,action:(x.archived||x.status==='ARCHIVED')?'restore':'archive'}">
            {{(x.archived||x.status==='ARCHIVED')?'Restaurar':'Archivar'}}
          </button>
          @if(kind==='generic-solutions'&&x.status==='DRAFT'){
            <button class="text-link" (click)="pending={record:x,action:'publish'}">Publicar</button>
            <a routerLink="/admin/documentos">Gestionar documentos</a>
          }
        </div></td></tr>
    }@empty{<tr><td colspan="4">Sin registros para esta búsqueda.</td></tr>}</tbody></table></div>
  }
  @if(pending;as operation){
    <div class="notice" role="status">
      Confirma {{actionLabel(operation.action)}} «{{operation.record.name_es}}».
      <div class="actions">
        <button class="button" [disabled]="busy()" (click)="applyAction()">Confirmar</button>
        <button class="button button-ghost" (click)="pending=null">Cancelar</button>
      </div>
    </div>
  }
</section>
@if(editing()){
  <form class="panel" (ngSubmit)="saveRecord()">
    <h2>{{editId?'Editar registro':'Nuevo registro'}}</h2>
    <div class="form-grid">
      @if(!editId){<label>Código<input name="code" [(ngModel)]="code" required maxlength="110"></label>}
      <label>Nombre<input name="name" [(ngModel)]="name" required maxlength="255"></label>
      @if(!editId&&parentKind()){
        <label>Clasificación superior<select name="parent" [(ngModel)]="parentId" required><option value="">Seleccionar</option>
          @for(parent of parents();track parent.id){<option [value]="parent.id">{{parent.code}} · {{parent.name_es}}</option>}
        </select></label>
      }
    </div>
    @if(kind==='generic-solutions'){
      <h3>Prestaciones</h3>
      @for(row of properties;track row;let i=$index){
        <fieldset class="component"><legend>Prestación {{i+1}}</legend><div class="form-grid">
          <label>Clave<input [name]="'property'+i" [(ngModel)]="row.code" required></label>
          <label>Valor<input [name]="'value'+i" [(ngModel)]="row.value" required></label>
          <label>Unidad<input [name]="'unit'+i" [(ngModel)]="row.unit"></label>
        </div><button type="button" class="text-link" (click)="properties.splice(i,1)">Retirar prestación</button></fieldset>
      }
      <button type="button" class="button button-ghost" (click)="properties.push({code:'',value:'',unit:''})">Añadir prestación</button>
    }
    <div class="actions">
      <button class="button" [disabled]="busy()||!name.trim()||(!editId&&(!code.trim()||!!parentKind()&&!parentId))">Guardar</button>
      <button type="button" class="button button-ghost" (click)="editing.set(false)">Cancelar</button>
    </div>
  </form>
}
<section class="panel"><h2>Nueva versión de plantilla</h2>
  <label>Subsistema<select [(ngModel)]="templateSubsystem"><option value="">Seleccionar</option>
    @for(sub of subsystems();track sub.id){<option [value]="sub.id">{{sub.code}} · {{sub.name_es}}</option>}
  </select></label>
  @for(field of templateFields;track field;let i=$index){
    <fieldset class="component"><legend>Campo {{i+1}}</legend><div class="form-grid">
      <label>Código<input [(ngModel)]="field.code"></label><label>Nombre<input [(ngModel)]="field.label"></label>
      <label>Tipo<select [(ngModel)]="field.type"><option value="number">Número</option><option value="text">Texto</option></select></label>
      <label>Unidad<input [(ngModel)]="field.unit"></label>
      <label><input type="checkbox" [(ngModel)]="field.required"> Campo obligatorio</label>
    </div><button class="text-link" (click)="templateFields.splice(i,1)">Retirar campo</button></fieldset>
  }
  <div class="actions"><button class="button button-ghost" (click)="addTemplateField()">Añadir campo</button>
    <button class="button" [disabled]="!templateSubsystem||!templateFields.length" (click)="saveTemplate()">Versionar plantilla</button></div>
</section>
}
@if(tab()==='audit'){<section class="panel"><h2>Registro de auditoría</h2>@for(a of logs();track a.id){<div class="file-row"><span>{{a.at}} · {{a.action}} · {{a.entity}}</span><span class="small">{{a.entity_id}}</span></div>}</section>}
}</div>`})
export class AdminComponent implements OnInit{
 api=inject(ApiService);session=inject(SessionService);route=inject(ActivatedRoute);tab=signal('reviews');queue=signal<Revision[]>([]);selected=signal<Revision|null>(null);error=signal('');info=signal('');logs=signal<AuditEntry[]>([]);
 policies:Record<string,Record<string,DocumentPolicy>>={};
 setPolicy(target:string,asset:string,policy:DocumentPolicy|null){
   const next=this.policies[target]||={};
   if(policy)next[asset]=policy;else delete next[asset];
 }
 filter='';batch=signal<string[]>([]);confirmed=false;busy=signal(false);
 batchResults=signal<{id:string;name:string;published:boolean;message?:string}[]>([]);
 reviewSection=signal<SolutionSection>('Visión general');
 private inspectId=0;
 inspecting=signal(false);
 catalogueLoading=signal(false);editing=signal(false);catalogueSearch='';editId='';
 reason='';kind='systems';code='';name='';parentId='';entries=signal<any[]>([]);parents=signal<Taxon[]>([]);
 subsystems=signal<Taxon[]>([]);templateSubsystem='';
 pending:{record:{id:string;name_es:string};action:'restore'|'archive'|'publish'}|null=null;
 properties:{code:string;value:string;unit:string}[]=[];
 private originalTechnical:Record<string,any>={};
 templateFields:{code:string;label:string;type:string;unit:string;required:boolean}[]=[];
 private catalogueRun=0;
 async ngOnInit(){
   if(!this.session.role())await this.session.restore();
   this.route.paramMap.subscribe(params=>{
     const section=params.get('section');
     this.tab.set(section==='taxonomia'?'catalogue':section==='auditoria'?'audit':'reviews');
     if(this.session.role()==='ADMIN')void this.load();
   });
 }
 async load(){
   const outcomes=await Promise.allSettled([
     this.api.listAll<Revision>('/admin/reviews').then(rows=>this.queue.set(rows)),
     this.api.list<AuditEntry>('/admin/audit-logs').then(rows=>this.logs.set(rows)),
     this.api.listAll<Taxon>('/subsystems').then(rows=>this.subsystems.set(rows))
   ]);
   const failure=outcomes.find(result=>result.status==='rejected');
   if(failure?.status==='rejected')this.error.set(problem(failure.reason));
   if(this.tab()==='catalogue')await this.loadCatalogue();
 }
 ifcCount(revision:Revision){return revision.assets.filter(asset=>asset.file_type==='IFC'&&asset.processing_status==='VALID').length}
 selectVisible(){this.batch.update(ids=>[...new Set([...ids,...this.filtered().map(row=>row.id)])].slice(0,100))}

 filtered(){const q=this.filter.trim().toLocaleLowerCase('es');return this.queue().filter(r=>r.name_es.toLocaleLowerCase('es').includes(q))}
 batchItems(){return this.queue().filter(r=>this.batch().includes(r.id))}
 toggle(id:string){this.batch.update(ids=>ids.includes(id)?ids.filter(x=>x!==id):[...ids,id].slice(0,100))}
 async inspect(id:string){
   const request=++this.inspectId;this.selected.set(null);this.inspecting.set(true);this.reason='';
   try{const result=await this.api.get<Revision>('/admin/reviews/'+id);if(request===this.inspectId)this.selected.set(result)}
   catch(e){if(request===this.inspectId)this.error.set(problem(e))}
   finally{if(request===this.inspectId)this.inspecting.set(false)}
 }
 async download(id:string,name:string){try{await this.api.download('/assets/'+id+'/download',name)}catch(e){this.error.set(problem(e))}}
 async decide(action:'approve'|'reject'|'corrections'){
   const r=this.selected();if(!r||this.busy())return;
   this.error.set('');this.busy.set(true);
   try{
     await this.api.post('/admin/reviews/'+r.id+'/'+action,{reason:this.reason,document_permissions:this.policies[r.id]});
     this.info.set(action==='approve'?'Revisión publicada':action==='reject'?'Revisión rechazada':'Correcciones solicitadas');
     this.selected.set(null);this.batch.update(ids=>ids.filter(id=>id!==r.id));this.reason='';await this.load();
   }catch(e){this.error.set(problem(e))}
   finally{this.busy.set(false)}
 }
 async approveBatch(){
   this.busy.set(true);this.error.set('');
   const names=new Map(this.batchItems().map(r=>[r.id,r.name_es]));
   try{
     const result=await this.api.post<{id:string;published:boolean;message?:string}[]>('/admin/reviews/bulk-approve',{ids:this.batch(),reason:this.reason,confirmed:this.confirmed,document_permissions:this.policies});
     this.batchResults.set(result.map(r=>({...r,name:names.get(r.id)||r.id})));
     this.batch.set(result.filter(r=>!r.published).map(r=>r.id));
     this.confirmed=false;this.selected.set(null);await this.load();
   }catch(e){this.error.set(problem(e))}
   finally{this.busy.set(false)}
 }
 parentKind(){
   const parents:Record<string,string>={subsystems:'systems',archetypes:'subsystems','generic-solutions':'archetypes',slots:'generic-solutions'};
   return parents[this.kind]||'';
 }
 async loadCatalogue(){
   const run=++this.catalogueRun,kind=this.kind,parent=this.parentKind();
   this.editing.set(false);this.pending=null;this.catalogueLoading.set(true);this.parents.set([]);
   const [entries,parents]=await Promise.allSettled([
     this.api.listAll('/admin/catalogue/'+kind),
     parent?this.api.listAll<Taxon>('/admin/catalogue/'+parent):Promise.resolve([])
   ]);
   if(run!==this.catalogueRun)return;
   this.entries.set(entries.status==='fulfilled'?entries.value:[]);
   this.parents.set(parents.status==='fulfilled'?parents.value.filter(row=>!row.archived):[]);
   for(const result of [entries,parents])if(result.status==='rejected')this.error.set(problem(result.reason));
   this.catalogueLoading.set(false);
 }
 visibleEntries(){
   const q=this.catalogueSearch.trim().toLocaleLowerCase('es');
   return this.entries().filter(row=>(row.code+' '+row.name_es).toLocaleLowerCase('es').includes(q));
 }
 beginCreate(){
   this.editId='';this.code='';this.name='';this.parentId='';this.properties=[];this.originalTechnical={};
   this.editing.set(true);
 }
 beginEdit(row:any){
   this.beginCreate();this.editId=row.id;this.name=row.name_es;
   this.originalTechnical=row.technical_data||{};
   this.properties=Object.entries(this.originalTechnical['properties']||{}).flatMap(([code,value]:[string,any])=>{
     const literal=value?.value;
     if(typeof literal!=='string'&&typeof literal!=='number')return [];
     return [{code,value:String(literal),unit:value.unit||''}];
   });
 }
 async saveRecord(){
   if(this.busy())return;
   const parentKeys:Record<string,string>={subsystems:'system_id',archetypes:'subsystem_id','generic-solutions':'archetype_id',slots:'generic_solution_id'};
   const record:Record<string,unknown>={name_es:this.name.trim()};
   if(!this.editId){
     record['code']=this.code.trim();
     if(parentKeys[this.kind])record[parentKeys[this.kind]]=this.parentId;
   }
   if(this.kind==='generic-solutions'){
     const originals=this.originalTechnical['properties']||{};
     const opaque=Object.fromEntries(Object.entries(originals).filter(([,entry]:[string,any])=>!['string','number'].includes(typeof entry?.value)));
     const keys=this.properties.map(row=>row.code.trim());
     if(keys.some(key=>!key)||new Set(keys).size!==keys.length||this.properties.some(row=>!row.value.trim())){
       this.error.set('Indica claves de prestación únicas y un valor para cada una.');return;
     }
     const properties=Object.fromEntries(this.properties.map((row,index)=>{
       const previous=originals[keys[index]];
       const value=previous&&String(previous.value)===row.value?previous.value:row.value.trim();
       return [keys[index],{...previous,value,unit:row.unit.trim()}];
     }));
     record['technical_data']={...this.originalTechnical,properties:{...opaque,...properties}};
   }
   this.busy.set(true);this.error.set('');
   try{
     const path='/admin/catalogue/'+this.kind;
     if(this.editId)await this.api.patch(path+'/'+this.editId,record);
     else await this.api.post(path,record);
     this.info.set('Registro guardado');await this.loadCatalogue();
   }catch(e){this.error.set(problem(e))}
   finally{this.busy.set(false)}
 }
 actionLabel(action:string){return action==='archive'?'el archivo de':action==='restore'?'la restauración de':'la publicación de'}
 async applyAction(){
   const item=this.pending;if(!item||this.busy())return;
   this.busy.set(true);this.error.set('');
   try{await this.api.post('/admin/catalogue/'+this.kind+'/'+item.record.id+'/'+item.action,{});await this.loadCatalogue()}
   catch(e){this.error.set(problem(e))}
   finally{this.busy.set(false)}
 }
 addTemplateField(){this.templateFields.push({code:'',label:'',type:'number',unit:'',required:false})}
 async saveTemplate(){
   const codes=this.templateFields.map(field=>field.code.trim());
   if(codes.some(code=>!code)||new Set(codes).size!==codes.length){this.error.set('Cada campo necesita un código único.');return;}
   try{await this.api.post('/admin/templates',{subsystem_id:this.templateSubsystem,fields:this.templateFields});this.info.set('Nueva versión de plantilla registrada')}
   catch(e){this.error.set(problem(e))}
 }
}
