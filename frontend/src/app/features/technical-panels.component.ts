import {referenceOf} from '../core/reference-model';
import {Component,Input,inject,OnChanges,signal} from '@angular/core';
import {DeclaredValuesComponent} from './declared-values.component';
import {CompositionDiagramComponent} from './composition-diagram.component';
import {DocumentGlyphComponent} from '../core/document-glyph.component';
import {PerformancePanelComponent} from './performance-panel.component';
import {ScenarioVisualsComponent} from './scenario-visuals.component';
import {ApiService,Asset,problem} from '../core/api';

@Component({selector:'app-technical-panels',standalone:true,imports:[DeclaredValuesComponent,CompositionDiagramComponent,PerformancePanelComponent,ScenarioVisualsComponent,DocumentGlyphComponent],template:`
@if(error()){<p class="error" role="alert">{{error()}}</p>}
@if(section==='Prestaciones'){
  <h2>Prestaciones</h2>
  <app-performance-panel [technical]="technical?.technical_performance || technical?.properties"/>
}
@if(section==='Composición'){
  <h2>Composición</h2>
  <app-composition-diagram [composition]="composition" [demo]="compositionScenario ? {composition:compositionScenario} : null"/>
  @if(composition.length){<h3>Detalle de la composición de origen</h3>}
  @for(layer of composition;track $index){
    <details class="component"><summary>{{layer.name_es || layer.name || layer.material || layer.code || 'Componente '+($index+1)}}</summary>
      @for(row of rows(layer.properties || layer);track $index){<dl class="property-row"><dt>{{row.label}}</dt><dd>{{row.value}}</dd></dl>}
    </details>
  }@empty{<p class="muted">Sin composición de origen declarada.</p>}
}
@if(section==='BIM'){
  <h2>Componentes IFC</h2>
  @for(asset of documents('IFC');track asset.id){
    @for(element of records()[asset.id]?.rows || [];track $index){
      <details class="component">
        <summary>{{element.name || element.ifc_class}} · #{{element.id || '–'}}</summary>
        <p class="small muted">{{element.ifc_class}} · {{element.global_id}}</p>
        @if(element.parent_id){<p class="small muted">Componente de #{{element.parent_id}}</p>}
        @if(element.materials?.length){<p>Materiales · {{element.materials.join(', ')}}</p>}
        @for(row of rows(element.psets);track $index){<dl class="property-row"><dt>{{row.label}}</dt><dd>{{row.value}}</dd></dl>}
        @for(row of rows(element.qto);track $index){<dl class="property-row"><dt>{{row.label}}</dt><dd>{{row.value}}</dd></dl>}
      </details>
    }@empty{<p class="muted">Sin componentes extraídos.</p>}
  }@empty{<p class="muted">Sin IFC público.</p>}
}
@if(section==='Economía'){
  <h2>Economía</h2>
  <app-scenario-visuals [scenario]="referenceOf(economic)" kind="economic"/>
  <app-declared-values [values]="declared(economic)" empty="Sin datos económicos declarados."/>
  <h3>Documentos y conceptos BC3</h3>
  @for(asset of documents('BC3');track asset.id){
    <p>{{asset.original_name}} · {{asset.processing_status}}</p>
    @if(asset.public_download_allowed && asset.processing_status==='VALID'){
      <a [href]="'/api/v1/assets/'+asset.id+'/regenerate'">Descargar BC3 regenerado</a>
    }
    <label>Filtrar conceptos <input #conceptQuery type="search" (change)="load(asset,1,conceptQuery.value)"></label>
    <div class="technical-scroll">
    @for(c of records()[asset.id]?.rows || [];track c.code){
      <details class="component"><summary>{{c.code}} · {{c.description}} · {{c.unit_price ?? '—'}} {{c.unit}}</summary>
        @if(c.text){<p>{{c.text}}</p>}
        @if(c.children?.length){
          <table><thead><tr><th>Concepto</th><th>Factor</th><th>Rendimiento</th></tr></thead>
          <tbody>@for(child of c.children;track $index){<tr><td>{{child.code}}</td><td>{{child.factor ?? '—'}}</td><td>{{child.quantity ?? '—'}}</td></tr>}</tbody></table>
        }
      </details>
    }
    </div>
  }@empty{<p class="muted">Sin BC3 público asociado a esta solución.</p>}
}
@if(section==='Ambiente'){
  <h2>Ambiente</h2>
  <app-scenario-visuals [scenario]="referenceOf(environmental)" kind="environmental"/>
  <app-declared-values [values]="declared(environmental)" empty="Sin datos ambientales declarados."/>
  <h3>Declaraciones EPD adjuntas</h3>
  @for(asset of documents('EPD');track asset.id){
    @if(summaries()[asset.id];as epd){
      <h3>{{epd.name || asset.original_name}}</h3>
      <div class="actions">
        <span class="tag">{{epd.module_count ?? '—'}} módulos</span>
        <span class="tag">{{epd.indicator_count ?? '—'}} indicadores</span>
        @if(asset.public_download_allowed){<a class="text-link" [href]="'/api/v1/documents/'+asset.id+'/download'">Descargar XML</a>}
      </div>
      <label>Filtrar por indicador o módulo
        <input type="search" #epdFilter placeholder="p. ej. GWP-total o A1-A3" (change)="load(asset,1,epdFilter.value)">
      </label>
      @for(row of rows({Programa:epd.programme,Registro:epd.registration,Vigencia:epd.valid_until,Perfil:epd.profile,
        Verificador:epd.verification?.declared_reviewer,Unidad:epd.declared_unit?.unit,'Validación':epd.validation});track $index){
        <dl class="property-row"><dt>{{row.label}}</dt><dd>{{row.value}}</dd></dl>
      }
      @for(warning of epd.warnings || [];track $index){<p class="notice">{{warning}}</p>}
      <div class="technical-scroll">
      <table><thead><tr><th>Indicador</th><th>Módulo</th><th>Escenario</th><th>Valor</th><th>Unidad</th></tr></thead>
      <tbody>@for(i of records()[asset.id]?.rows || [];track $index){<tr><td>{{i.indicator || '—'}}</td><td>{{i.module}}</td><td>{{i.scenario || '—'}}</td><td>{{i.value ?? 'Ausente'}}</td><td>{{i.unit || '—'}}</td></tr>}
      @empty{<tr><td colspan="5">Sin valores para esta selección.</td></tr>}</tbody></table>
      </div>
    }
  }@empty{<p class="muted">Sin EPD pública asociada a esta solución.</p>}
}
@if(domain();as kind){
  @for(asset of documents(kind);track asset.id){
    @if(records()[asset.id];as result){
      @if(result.total>50){
        <div class="actions"><span>{{asset.original_name}} · {{result.total}} resultados</span>
        <button class="button button-ghost" [disabled]="result.page<=1" (click)="load(asset,result.page-1,result.q)">Anterior</button>
        <button class="button button-ghost" [disabled]="result.page*50>=result.total" (click)="load(asset,result.page+1,result.q)">Siguiente</button></div>
      }
    }
  }
}
@if(section==='Documentos'){
  <h2>Documentación</h2>
  @for(a of assets;track a.id){<div class="file-row"><span class="metra-file-icon"><app-document-glyph [format]="a.file_type"/>{{a.file_type}} · {{a.original_name}}</span>
    @if(a.public_download_allowed){<a [href]="'/api/v1/assets/'+a.id+'/download'">Descargar original</a>}@else{<span>Solo visualización</span>}
  </div>}@empty{<p class="muted">Sin documentos públicos.</p>}
}
`})
export class TechnicalPanelsComponent implements OnChanges {
  @Input() section='Prestaciones';
  @Input() technical: any;
  @Input() compositionScenario:any;
  @Input() economic:any;
  @Input() environmental:any;
  @Input() composition: any[]=[];
  @Input() assets: Asset[]=[];
  private api=inject(ApiService);
  private epoch=0;
  private requests=new Map<string,number>();
  records=signal<Record<string,{rows:any[];total:number;page:number;q:string}>>({});
  summaries=signal<Record<string,any>>({});
  error=signal('');
  readonly referenceOf=referenceOf;
  declared(value:any){
    if(!value||typeof value!=='object')return value;
    const {illustrative,reference,...declared}=value;return declared;
  }
  documents(type:string){return this.assets.filter(a=>a.file_type===type)}
  domain(){return this.section==='BIM'?'IFC':this.section==='Economía'?'BC3':this.section==='Ambiente'?'EPD':''}
  ngOnChanges(){
    ++this.epoch;
    this.error.set('');this.records.set({});this.summaries.set({});
    for(const asset of this.documents(this.domain())){
      if(asset.processing_status!=='VALID')continue;
      void this.load(asset,1);
      if(asset.file_type==='EPD')void this.summary(asset);
    }
  }
  async summary(asset:Asset){
    const epoch=this.epoch;
    try{
      const summary=await this.api.get('/documents/'+asset.id+'/summary');
      if(epoch===this.epoch)this.summaries.update(old=>({...old,[asset.id]:summary}));
    }catch(e){if(epoch===this.epoch)this.error.set(problem(e))}
  }
  async load(asset:Asset,page:number,q=''){
    const epoch=this.epoch;
    const request=(this.requests.get(asset.id)||0)+1;
    this.requests.set(asset.id,request);
    try{
      const result=await this.api.page<any>('/documents/'+asset.id+'/data',{page,page_size:50,q});
      if(epoch===this.epoch&&request===this.requests.get(asset.id))this.records.update(old=>({...old,[asset.id]:{rows:result.data,total:result.meta?.total||0,page,q}}));
    }catch(e){if(epoch===this.epoch)this.error.set(problem(e))}
  }
  rows(value:unknown,prefix='',depth=0):{label:string;value:string}[]{
    if(value===null||value===undefined||depth>4)return [];
    if(typeof value!=='object')return prefix?[{label:prefix,value:String(value)}]:[];
    return Object.entries(value).filter(([key])=>key!=='id').flatMap(([key,child])=>
      this.rows(child,prefix?prefix+' / '+key:key,depth+1));
  }
}
