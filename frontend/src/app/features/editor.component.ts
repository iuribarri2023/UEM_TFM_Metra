import {SubsystemTemplate,TemplateField} from '../core/canonical';
import {Component,inject,OnInit,signal} from '@angular/core';
import {ActivatedRoute,RouterLink} from '@angular/router';
import {FormsModule} from '@angular/forms';
import {ApiService,Product,Revision,Generic,problem} from '../core/api';
import {BudgetsComponent} from './budgets.component';
import {DocumentPolicy,DocumentPolicyComponent} from './document-policy.component';
import {TechnicalPanelsComponent} from './technical-panels.component';
import {DeclaredInput,DeclaredValueEditorComponent,editableValues} from './declared-value-editor.component';
import {ViewerHostComponent} from './viewer-host.component';
@Component({standalone:true,imports:[FormsModule,RouterLink,ViewerHostComponent,BudgetsComponent,DocumentPolicyComponent,TechnicalPanelsComponent,DeclaredValueEditorComponent],template:`<div class="container content portal-content"><a class="back" routerLink="/fabricante">← Mis productos</a><span class="eyebrow">Ficha y control editorial</span><h1>{{item()?.revisions?.[0]?.name_es||'Editar producto'}}</h1>
@if(error()){<p class="error">{{error()}}</p>}@if(message()){<p class="notice">{{message()}}</p>}
@if(item();as p){<div class="panel"><div class="file-row"><div><strong>Estado: {{revision()?.status}}</strong><p class="muted small">Publicada: {{p.published?.number||'ninguna'}} · Disponibilidad: {{p.availability}}</p></div>
@if(revision()?.status==='APPROVED'||revision()?.status==='REJECTED'){<button class="button" (click)="newVersion()">Nueva revisión</button>}
<select [ngModel]="p.availability" (ngModelChange)="availability($event)" aria-label="Disponibilidad del producto"><option>ACTIVE</option><option>SUSPENDED</option><option>ARCHIVED</option></select></div>
@if(revision()?.rejection_reason){<p class="error">Motivo del rechazo: {{revision()?.rejection_reason}}</p>}
</div>
@if(revision()?.status==='DRAFT'){
<nav class="wizard-tabs editor-nav" aria-label="Secciones de edición">@for(t of steps;track $index){<button [class.active]="step()===$index" [attr.aria-current]="step()===$index?'step':null" (click)="step.set($index)">{{($index+1)}} · {{t}}</button>}</nav>
<section class="panel">
@if(step()===0){<h2>1. Clasificación técnica</h2><p>Subsistema obligatorio: <strong>{{subsystemName()||'Cargando clasificación…'}}</strong></p><label>Referencias genéricas compatibles (selección múltiple)<select multiple [ngModel]="genericIds" (ngModelChange)="genericIds=$event" size="5">@for(g of generics();track g.id){<option [value]="g.id">{{g.code}} — {{g.name_es}}</option>}</select></label><p class="small muted">Se comprueba nuevamente la compatibilidad al guardar y enviar.</p>}
@if(step()===1){<h2>2. Identificación</h2><label>Nombre<input [(ngModel)]="name"></label><label>Referencia comercial<input [(ngModel)]="reference"></label><label>Descripción<textarea [(ngModel)]="description"></textarea></label><label>Unidad funcional<input [(ngModel)]="unit"></label>}
@if(step()===2){<h2>3. Prestaciones por plantilla</h2><p class="muted">Plantilla v{{template()?.version}}. Para cada propiedad se usa unidad canónica.</p>
@for(field of template()?.fields;track field.code){<div class="field-property"><label>{{field.label||field.code}}{{field.required?' *':''}} ({{field.unit}})@if(field.type==='boolean'){
  <input type="checkbox" [checked]="props[field.code]?.value===true" (change)="updateProperty(field,$event)">
}@else if(field.enum?.length){
  <select [value]="props[field.code]?.value??''" (change)="updateProperty(field,$event)"><option value="">Sin declarar</option>
    @for(option of field.enum;track $index){<option [value]="option">{{option}}</option>}
  </select>
}@else{
  <input [type]="field.type==='number'?'number':'text'" [value]="props[field.code]?.value??''" (change)="updateProperty(field,$event)" [attr.min]="field.min??null" [attr.max]="field.max??null">
}</label></div>}
@if(!template()?.fields?.length){<p class="notice">Este subsistema aún no tiene una plantilla definida. La administración puede versionarla.</p>}}
@if(step()===3){
<h2>4. Composición</h2>
<p>Ordena las capas según la secuencia constructiva. El espesor se registra en milímetros.</p>
@if(inheritedComposition().length){
  <app-technical-panels section="Composición" [composition]="inheritedComposition()"/>
  <p>La composición importada conserva sus campos de origen.</p>
}@else{
  @for(layer of composition;track layer;let index=$index){
    <fieldset class="component">
      <legend>Capa {{index+1}}</legend>
      <div class="form-grid">
        <label>Componente<input [(ngModel)]="layer.name" maxlength="180"></label>
        <label>Material<input [(ngModel)]="layer.material" maxlength="180"></label>
        <label>Espesor (mm)<input type="number" [(ngModel)]="layer.thickness_mm" min="0.001"></label>
      </div>
      <div class="actions">
        <button class="text-link" [disabled]="index===0" (click)="moveLayer(index,-1)">Subir capa</button>
        <button class="text-link" [disabled]="index===composition.length-1" (click)="moveLayer(index,1)">Bajar capa</button>
        <button class="text-link" (click)="composition.splice(index,1)">Retirar capa</button>
      </div>
    </fieldset>
  }@empty{<p class="muted">Todavía no hay capas declaradas.</p>}
  <button class="button button-ghost" [disabled]="composition.length>=100" (click)="addLayer()">Añadir capa</button>
}
}
@if(step()===4){<h2>5. Modelos y documentos</h2><p>IFC obligatorio. BC3 y XML EPD opcionales, pero serán validados si se adjuntan.</p><input #uploadInput type="file" accept=".ifc,.bc3,.zip,.xml" aria-label="Archivo IFC, BC3 o XML"><button class="button" (click)="upload(uploadInput)">Subir y validar</button>
@for(a of revision()?.assets;track a.id){
<app-document-policy [asset]="a" (policy)="stagePolicy(a.id,$event)"/>
<div class="actions">
<button class="button button-ghost" (click)="checkDocument(a.id)">Consultar estado</button>
@if(a.processing_status==='INVALID'){<button class="text-link" (click)="documentAction(a.id,'retry')">Reintentar</button>}
@if(a.processing_status==='PENDING'){<button class="text-link" (click)="documentAction(a.id,'cancel')">Cancelar</button>}
<button class="text-link" [disabled]="!policies[a.id]" (click)="savePolicy(a.id)">Guardar permisos</button>
<button class="text-link" (click)="remove(a.id)">Retirar</button></div>
@if(a.file_type==='IFC'&&a.processing_status==='VALID'){<button class="text-link" (click)="draftViewer.set(draftViewer()===a.id?'':a.id)">Inspeccionar y vincular</button>}
@if(draftViewer()===a.id&&a.processing_status==='VALID'){
  <app-viewer-host [assetId]="a.id" [revisionId]="revision()?.id||''" [editable]="true" [targets]="linkTargets()"/>
}
@if(a.file_type==='IFC'){<p class="small muted">La autorización de visor permite recuperar técnicamente los bytes.</p>}}
}
@if(step()===5){<h2>6. Economía y ambiente</h2>
<p class="muted">Las magnitudes declaradas se conservan junto con los datos históricos y los documentos asociados.</p>
<app-declared-value-editor heading="Datos económicos" [rows]="economic"/>
<app-declared-value-editor heading="Datos ambientales" [rows]="environmental"/>
}
@if(step()===6){<h2>7. Revisar y enviar</h2>
<ul class="editor-checklist">
  <li>{{genericIds.length}} referencias genéricas seleccionadas</li>
  <li>{{propertyCount()}} prestaciones declaradas</li>
  <li>{{inheritedComposition().length||composition.length}} capas de composición</li>
  <li>{{ifcCount()}} modelos IFC válidos</li>
</ul>
<button class="button" [disabled]="busy()" (click)="submit()">Enviar a revisión administrativa</button>}
<div class="actions"><button class="button button-light" [disabled]="busy()" (click)="save()">Guardar borrador</button>
<button class="button button-ghost" [disabled]="step()===0" (click)="step.set(step()-1)">Anterior</button>
<button class="button button-ghost" [disabled]="step()===steps.length-1" (click)="step.set(step()+1)">Siguiente</button></div></section>
}@else{<section class="panel"><h2>Historial de la revisión</h2><p>Las revisiones enviadas, aprobadas y rechazadas son inmutables.</p>
@for(a of revision()?.assets;track a.id){<div class="file-row">{{a.file_type}} · {{a.original_name}} @if(a.file_type==='IFC'){<app-viewer-host [assetId]="a.id"/>}</div>}</section>}
<app-budgets [productId]="p.id" [editable]="revision()?.status==='DRAFT'" [draftId]="revision()?.id||''"/>
<section class="panel revision-history"><h2>Histórico de versiones</h2>
@if(restoreSource();as source){
  <div class="notice" role="status">Crear un borrador basado en la revisión #{{source.number}}.
    Los permisos de difusión del borrador se deben autorizar de nuevo.
    <div class="actions"><button class="button" [disabled]="busy()" (click)="newVersion(source.id)">Crear borrador</button>
      <button class="button button-ghost" (click)="restoreSource.set(null)">Cancelar</button></div>
  </div>
}@for(r of p.revisions;track r.id){<details class="component"><summary>#{{r.number}} · {{r.name_es}} · {{r.status}} {{p.published_revision_id===r.id?'· Publicada':''}}</summary>
   @if(parentNumber(p,r);as parent){<p>Deriva de la revisión #{{parent}}</p>}
   @if(r.message){<p>{{r.message}}</p>}
   @if((revision()?.status==='APPROVED'||revision()?.status==='REJECTED')&&(r.status==='APPROVED'||r.status==='REJECTED')){
     <button class="text-link" (click)="restoreSource.set(r)">Crear borrador desde esta revisión</button>
   }
   @if(r.created_at){<p>{{r.created_at.slice(0,10)}}</p>}
   @if(r.created_by){<p>Autor registrado · {{r.created_by}}</p>}
   @for(a of r.assets;track a.id){<div class="file-row"><span>{{a.original_name}}</span><button class="text-link" (click)="download(a.id,a.original_name)">Descargar</button></div>}
</details>}
@if((p.revisions?.length||0)>1){
  <h3>Comparar revisiones</h3>
  <div class="catalog-controls">
    <label>Revisión de origen<select [(ngModel)]="compareFrom"><option value="">Seleccionar</option>
      @for(r of p.revisions;track r.id){<option [value]="r.id">#{{r.number}} · {{r.name_es}}</option>}
    </select></label>
    <label>Revisión de destino<select [(ngModel)]="compareTo"><option value="">Seleccionar</option>
      @for(r of p.revisions;track r.id){<option [value]="r.id">#{{r.number}} · {{r.name_es}}</option>}
    </select></label>
  </div>
  @if(compareFrom&&compareTo&&compareFrom!==compareTo){
    <div class="technical-scroll"><table>
      <thead><tr><th>Campo</th><th>Origen</th><th>Destino</th></tr></thead>
      <tbody>@for(change of changes(p);track change.label){
        <tr><th>{{change.label}}</th><td>{{change.before}}</td><td>{{change.after}}</td></tr>
      }@empty{<tr><td colspan="3">Sin cambios en los campos comparados.</td></tr>}</tbody>
    </table></div>
  }
}
</section>}
</div>`})
export class EditorComponent implements OnInit{
 api=inject(ApiService);route=inject(ActivatedRoute);item=signal<Product|null>(null);revision=signal<Revision|null>(null);generics=signal<Generic[]>([]);template=signal<SubsystemTemplate|null>(null);error=signal('');message=signal('');busy=signal(false);
 draftViewer=signal('');restoreSource=signal<Revision|null>(null);
 linkTargets(){return (this.revision()?.assets||[]).filter(asset=>asset.file_type!=='IFC'&&asset.processing_status==='VALID')}
 subsystemName=signal('');inheritedComposition=signal<unknown[]>([]);
 composition:{name:string;material:string;thickness_mm:number|null}[]=[];
 economic:DeclaredInput[]=[];
 environmental:DeclaredInput[]=[];
 steps=['Clasificación','Datos generales','Prestaciones','Composición','Archivos','Economía y ambiente','Enviar'];step=signal(0);genericIds:string[]=[];name='';reference='';description='';unit='m2';props:any={};
 get id(){return this.route.snapshot.paramMap.get('id')||''}
 async ngOnInit(){await this.reload()}
 async reload(preserveDraft=false){try{const p=await this.api.get<Product>('/manufacturer/products/'+this.id);this.item.set(p);const r=p.revisions?.[0]||null;this.revision.set(r);
 if(r&&!preserveDraft){
 this.economic=editableValues(r.economic_data);this.environmental=editableValues(r.environmental_data);
 const layers=r.technical_data?.composition;
 const source=Array.isArray(layers)?layers:[];
 const hasNativeLayers=source.every(layer=>layer&&typeof layer.name==='string'&&Object.keys(layer).every(key=>['name','material','thickness_mm'].includes(key)));
 this.inheritedComposition.set(hasNativeLayers?[]:source);
 this.composition=hasNativeLayers?source.map(layer=>({name:layer.name,material:layer.material||'',thickness_mm:layer.thickness_mm??null})):[];
 this.name=r.name_es;this.reference=r.commercial_reference;this.description=r.description;this.unit=r.functional_unit;this.props=r.technical_data?.properties||{};this.genericIds=[...r.generic_solution_ids]}
 this.generics.set((await this.api.list<Generic>('/generic-solutions',{page_size:100,subsystem_id:p.subsystem_id})));
 const subs=await this.api.listAll<{id:string;code:string;name_es:string}>('/subsystems');const sub=subs.find(s=>s.id===p.subsystem_id);
 this.subsystemName.set(sub?.name_es||'');const code=sub?.code;
 if(code){
   try{this.template.set(await this.api.get<SubsystemTemplate>('/data-templates/'+code,r?.template_version?{version:r.template_version}:{}))}
   catch{this.template.set(await this.api.get<SubsystemTemplate>('/data-templates/'+code))}
 }
 }catch(e){this.error.set(problem(e))}}
 updateProperty(field:TemplateField,event:Event){
   const input=event.target as HTMLInputElement;
   const raw=input.value.trim();
   const next={...this.props};
   if(!raw&&field.type!=='boolean')delete next[field.code];
   else next[field.code]={value:field.type==='boolean'?input.checked:field.type==='number'?Number(raw):raw,unit:field.unit};
   this.props=next;
 }

 compareFrom='';compareTo='';
 changes(product:Product){
  const from=product.revisions?.find(row=>row.id===this.compareFrom);
  const to=product.revisions?.find(row=>row.id===this.compareTo);
  if(!from||!to)return [];
  const properties=(r:Revision)=>r.technical_data?.properties||{};
  const value=(entry:unknown)=>entry==null?'—':typeof entry==='string'?entry:JSON.stringify(entry);
  const documentSet=(r:Revision,type:string)=>r.assets.filter(a=>a.file_type===type)
    .map(a=>a.original_name+' ['+a.id.slice(0,8)+']').sort().join(', ');
  const result:{label:string;before:string;after:string}[]=[];
  const compare=(label:string,left:unknown,right:unknown)=>{
    const before=value(left),after=value(right);
    if(before!==after)result.push({label,before,after});
  };
  compare('Nombre',from.name_es,to.name_es);
  compare('Descripción',from.description,to.description);
  compare('Referencia comercial',from.commercial_reference,to.commercial_reference);
  compare('Unidad funcional',from.functional_unit,to.functional_unit);
  compare('Plantilla',from.template_version,to.template_version);
  compare('Referencias genéricas',[...from.generic_solution_ids].sort(),[...to.generic_solution_ids].sort());
  compare('Composición',from.technical_data?.composition,to.technical_data?.composition);
  compare('Datos económicos',from.economic_data,to.economic_data);
  compare('Datos ambientales',from.environmental_data,to.environmental_data);
  for(const key of new Set([...Object.keys(properties(from)),...Object.keys(properties(to))])){
    compare(key,properties(from)[key],properties(to)[key]);
  }
  for(const type of ['IFC','BC3','EPD'])compare(type,documentSet(from,type),documentSet(to,type));
  return result;
 }
 parentNumber(p:Product,r:Revision){return p.revisions?.find(item=>item.id===r.parent_id)?.number}
 async download(id:string,name:string){try{await this.api.download('/assets/'+id+'/download',name)}catch(e){this.error.set(problem(e))}}
 addLayer(){this.composition.push({name:'',material:'',thickness_mm:null})}
 moveLayer(index:number,delta:number){
   const [layer]=this.composition.splice(index,1);
   this.composition.splice(index+delta,0,layer);
 }
 propertyCount(){return Object.keys(this.props).length}
 ifcCount(){return (this.revision()?.assets||[]).filter(x=>x.file_type==='IFC'&&x.processing_status==='VALID').length}
 private declaredPayload(rows:DeclaredInput[]){
   return rows.map(row=>{
     const raw=row.value.trim();
     const value=row.type==='number'?Number(raw.replace(',','.')):raw;
     if(!row.label.trim()||!raw||(typeof value==='number'&&!Number.isFinite(value))){
       this.step.set(5);
       throw new Error('Revisa el nombre y valor de las magnitudes económicas y ambientales.');
     }
     return {label:row.label.trim(),value,unit:row.unit.trim(),source:row.source.trim()};
   });
 }
 async save(){const r=this.revision();if(!r||r.status!=='DRAFT'||this.busy())return;
 this.busy.set(true);this.error.set('');try{await this.api.patch('/manufacturer/revisions/'+r.id,{name_es:this.name,commercial_reference:this.reference,description:this.description,functional_unit:this.unit,technical_data:{properties:this.props},generic_solution_ids:this.genericIds,economic_values:this.declaredPayload(this.economic),environmental_values:this.declaredPayload(this.environmental),...(!this.inheritedComposition().length?{composition:this.composition}:{})});this.message.set('Borrador guardado')}catch(e){this.error.set(problem(e))}finally{this.busy.set(false)}}
 async upload(input:HTMLInputElement){const r=this.revision();const file=input.files?.[0];if(!r||!file)return;try{await this.api.upload('/manufacturer/revisions/'+r.id+'/assets',file);input.value='';await this.reload(true);this.message.set('Archivo en cola. Consulta su estado antes de enviar.') }catch(e){this.error.set(problem(e))}}
 policies:Record<string,DocumentPolicy>={};
 stagePolicy(id:string,policy:DocumentPolicy|null){if(policy)this.policies[id]=policy;else delete this.policies[id]}
 async savePolicy(id:string){
  const revision=this.revision(),policy=this.policies[id];
  if(!revision||!policy)return;
  try{await this.api.patch('/manufacturer/revisions/'+revision.id+'/assets/'+id,policy);delete this.policies[id];await this.reload(true)}
  catch(e){this.error.set(problem(e))}
 }
 async checkDocument(id:string){
  try{
   const state=await this.api.get<{state:string;progress:number;warnings:string[]}>('/documents/'+id+'/processing');
   this.message.set([state.state+' · '+state.progress+'%',...state.warnings].join(' · '));
   this.revision.update(revision=>revision?{...revision,assets:revision.assets.map(asset=>asset.id===id?{...asset,processing_status:state.state==='CANCELLED'?'INVALID':state.state}:asset)}:null);
  }catch(e){this.error.set(problem(e))}
 }
 async documentAction(id:string,action:'retry'|'cancel'){
  try{await this.api.post('/documents/'+id+'/'+action,{});await this.checkDocument(id)}catch(e){this.error.set(problem(e))}
 }
 async remove(id:string){try{await this.api.remove('/manufacturer/revisions/'+this.revision()!.id+'/assets/'+id);await this.reload(true)}catch(e){this.error.set(problem(e))}}
 async submit(){
  const revision=this.revision();if(!revision||this.busy())return;
  await this.save();if(this.error())return;
  this.busy.set(true);
  try{
    await this.api.post('/manufacturer/revisions/'+revision.id+'/submit',{});
    await this.reload();this.message.set('Revisión enviada al administrador');
  }catch(e){this.error.set(problem(e))}
  finally{this.busy.set(false)}
 }
 async newVersion(source?:string){
  if(this.busy())return;
  this.busy.set(true);this.error.set('');
  try{
    await this.api.post('/manufacturer/products/'+this.id+'/revisions',source?{source_revision_id:source}:{});
    this.restoreSource.set(null);this.step.set(0);await this.reload();
  }catch(e){this.error.set(problem(e))}
  finally{this.busy.set(false)}
 }
 async availability(value:string){try{await this.api.patch('/manufacturer/products/'+this.id,{availability:value});await this.reload(true)}catch(e){this.error.set(problem(e))}}
}
