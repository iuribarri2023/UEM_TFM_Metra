import {referenceOf} from '../core/reference-model';
import {ReferenceComparisonComponent} from './reference-comparison.component';
import {CompositionDiagramComponent} from './composition-diagram.component';
import {ArchitecturalGlyphComponent} from '../core/architectural-glyph.component';
import {Component,DestroyRef,inject,OnInit,computed,signal} from '@angular/core';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {ActivatedRoute,Router,RouterLink} from '@angular/router';
import {FormsModule} from '@angular/forms';
import {ApiService,Product,Generic,Taxon,problem} from '../core/api';
import {ComparisonStateService,normalizeComparisonIds,SolutionKey,MAX_COMPARISON_ITEMS} from '../core/comparison-state.service';
import {buildComparisonMatrix,ComparedResult,ComparisonSection} from '../core/comparison-matrix';

interface Choice {subsystem:string;key:SolutionKey;name:string;code:string;kind:'Genérica'|'Comercial'}
@Component({standalone:true,imports:[FormsModule,RouterLink,ReferenceComparisonComponent,CompositionDiagramComponent,ArchitecturalGlyphComponent],template:`
<div class="container content compare-workbench">
  <a class="back" routerLink="/catalogo">← Volver al catálogo</a>
  <header class="compare-heading"><span class="eyebrow">Análisis técnico</span><h1>Comparador de dos soluciones</h1>
    <p>Dos posiciones independientes. Se admiten referencias genéricas, productos comerciales y comparaciones mixtas.
       Las diferencias se basan exclusivamente en los datos declarados.</p></header>
  <section class="panel" aria-label="Selección de soluciones">
    <div class="compare-pickers compare-context">
      <label>Sistema<select [ngModel]="system()" (ngModelChange)="chooseSystem($event)">
        <option value="">Seleccionar sistema</option>
        @for(item of systems();track item.id){<option [value]="item.id">{{item.name_es}}</option>}
      </select></label>
      <label>Subsistema<select [ngModel]="subsystem()" (ngModelChange)="chooseSubsystem($event)" [disabled]="!system()">
        <option value="">Seleccionar subsistema</option>
        @for(item of eligibleSubsystems();track item.id){<option [value]="item.id">{{item.name_es}}</option>}
      </select></label>
    </div>
    <div class="compare-pickers">
      @for(index of positions;track index){
        <label>Solución {{index===0?'A':'B'}}
          <select [ngModel]="comparison.slots()[index]||''" (ngModelChange)="select(index,$event)" [disabled]="!subsystem()" [attr.aria-label]="'Solución '+(index===0?'A':'B')">
            <option value="">Seleccionar solución</option>
            @for(choice of choices();track choice.key){<option [value]="choice.key" [disabled]="comparison.items().includes(choice.key)&&comparison.slots()[index]!==choice.key">
              {{choice.kind}} · {{choice.name}} ({{choice.code}})
            </option>}
          </select>
          @if(comparison.slots()[index]){<button type="button" class="text-link" (click)="remove(index)">Retirar {{index===0?'A':'B'}}</button>}
        </label>
      }
    </div>
    <div class="compare-actions">
      <button type="button" class="button button-ghost" (click)="swap()" [disabled]="comparison.items().length!==2">Intercambiar A ↔ B</button>
      <button type="button" class="button button-ghost" (click)="clear()" [disabled]="!comparison.items().length">Limpiar</button>
      <button type="button" class="button" (click)="copyUrl()" [disabled]="comparison.items().length!==2">Copiar enlace</button>
    </div>
    <p class="small muted">{{comparison.items().length}} de {{maxItems}} soluciones seleccionadas. Una tercera requiere sustituir A o B.</p>
    @if(notice()){<p class="notice" role="status">{{notice()}}</p>}
  </section>
  @if(error()){<p class="error" role="alert">{{error()}}</p>}
  @if(loading()){<p class="notice" role="status">Cargando datos de comparación…</p>}
  @if(comparison.items().length!==2){<p class="panel">Selecciona dos soluciones para mostrar la matriz técnica.</p>}
  @if(result();as report){
    <section aria-label="Comparación técnica">
      <div class="compare-result-head"><div><span class="eyebrow">Matriz comparativa</span><h2>{{report.solutions[0].name}} / {{report.solutions[1].name}}</h2></div>
        <label class="compare-difference-toggle"><input type="checkbox" [(ngModel)]="onlyDifferences"> Mostrar solo diferencias</label>
      </div>
      @for(warning of report.warnings;track warning){<p class="notice compare-warning">{{warning}}</p>}
      <p class="small muted">«—» indica ausencia de datos. Las diferencias no constituyen una clasificación ni certificación de prestaciones.</p>
      <div class="compare-alternatives">
        @for(solution of report.solutions;track solution.key){
          <article class="compare-alternative compare-identity">
            @if(thumbnail(solution.assets);as image){
              <img [src]="'/api/v1/documents/'+image.id+'/thumbnail'" alt="Miniatura IFC autorizada">
            }@else{<app-architectural-glyph [system]="solution.canonical?.template?.code||solution.code"/>}
            <div><span class="eyebrow">Solución {{$index===0?'A':'B'}}</span><h3>{{solution.name}}</h3>
              <p>{{solution.system}} · {{solution.subsystem}}<br>{{solution.manufacturer||'Referencia genérica'}}</p>
            </div>
          </article>
        }
      </div>
      <label class="compare-filter">Sección <select [(ngModel)]="filter">
        <option value="">Todas</option>
        @for(section of sections();track section.title){<option [value]="section.title">{{section.title}}</option>}
      </select></label>
      @if(!filter||filter==='Composición'){
        <h3>Composición comparada</h3>
        <div class="compare-alternatives">@for(solution of report.solutions;track solution.key){
          <article class="compare-alternative"><span class="eyebrow">Solución {{$index===0?'A':'B'}}</span>
            <app-composition-diagram [composition]="compositionOf(solution.composition)"/>
          </article>
        }</div>
      }
      @if(!filter||filter==='Economía'){
        <h3>Coste de referencia</h3>
        <app-reference-comparison [a]="referenceOf(report.solutions[0].economic_data)"
                                  [b]="referenceOf(report.solutions[1].economic_data)"/>
      }
      @if(!filter||filter==='Ambiente'){
        <h3>GWP de referencia por módulos</h3>
        <app-reference-comparison [a]="referenceOf(report.solutions[0].environmental_data)"
                                  [b]="referenceOf(report.solutions[1].environmental_data)"/>
      }
      @if(!filter||filter==='Prestaciones'){
        <h3>Prestaciones lado a lado</h3>
        <div class="compare-performance">@for(row of performance();track row.key){
          <article><h4>{{row.label}}</h4><div class="compare-alternatives">
            <div><small>A</small><strong>{{row.a.value}} {{row.a.unit==='unit'?'':row.a.unit}}</strong><span>{{row.a.source}}</span></div>
            <div><small>B</small><strong>{{row.b.value}} {{row.b.unit==='unit'?'':row.b.unit}}</strong><span>{{row.b.source}}</span></div>
          </div></article>
        }</div>
      }
      @for(section of sections();track section.title){@if(!filter||filter===section.title){
        <details class="compare-section">
          <summary><strong>{{section.title}}</strong><span>{{visibleRows(section).length}} propiedades</span></summary>
          <div class="technical-scroll compare-scroll" role="region" [attr.aria-label]="'Matriz de '+section.title" tabindex="0">
            <table class="work-table compare-matrix">
              <colgroup><col class="compare-col-label"><col class="compare-col-solution"><col class="compare-col-solution"><col class="compare-col-observation"></colgroup>
              <thead><tr><th scope="col">Propiedad</th><th scope="col">A · {{report.solutions[0].code}}</th>
                <th scope="col">B · {{report.solutions[1].code}}</th><th scope="col">Análisis</th></tr></thead>
              <tbody>
                @for(row of visibleRows(section);track row.key){<tr [class.compare-different]="row.different">
                  <th scope="row">{{row.label}}</th>
                  <td>{{row.a.value}} @if(row.a.unit){<small>{{row.a.unit}}</small>} @if(row.a.source){<span class="compare-source">Origen: {{row.a.source}}</span>}</td>
                  <td>{{row.b.value}} @if(row.b.unit){<small>{{row.b.unit}}</small>} @if(row.b.source){<span class="compare-source">Origen: {{row.b.source}}</span>}</td>
                  <td class="compare-note">{{row.note}}</td>
                </tr>}@empty{<tr><td colspan="4">Sin propiedades que cumplan el filtro.</td></tr>}
              </tbody>
            </table>
          </div>
        </details>
      }}
    </section>
  }
</div>`})
export class CompareComponent implements OnInit {
  readonly comparison=inject(ComparisonStateService);
  readonly maxItems=MAX_COMPARISON_ITEMS;
  readonly positions=[0,1];
  private api=inject(ApiService);
  private route=inject(ActivatedRoute);
  private router=inject(Router);
  private destroy=inject(DestroyRef);
  private allChoices=signal<Choice[]>([]);
  systems=signal<Taxon[]>([]);
  subsystems=signal<Taxon[]>([]);
  system=signal('');
  subsystem=signal('');
  eligibleSubsystems=computed(()=>this.subsystems().filter(sub=>sub.system_id===this.system()));
  choices=computed(()=>this.allChoices().filter(choice=>choice.subsystem===this.subsystem()));
  result=signal<ComparedResult|null>(null);
  filter='';
  readonly referenceOf=referenceOf;
  thumbnail(assets:{id:string;thumbnail_available?:boolean;public_view_allowed?:boolean}[]){
    return assets.find(asset=>asset.thumbnail_available&&asset.public_view_allowed);
  }
  compositionOf(value:unknown){return Array.isArray(value)?value:[];}
  performance(){
    const section=this.sections().find(x=>x.title==='Prestaciones');
    return section?this.visibleRows(section).filter(row=>row.a.raw!==null||row.b.raw!==null).slice(0,8):[];
  }
  sections=computed(()=>this.result()?buildComparisonMatrix(this.result()!):[]);
  error=signal('');notice=signal('');loading=signal(false);
  onlyDifferences=false;
  private sequence=0;
  async ngOnInit(){
    try {
      const [generics,products,systems,subsystems]=await Promise.all([
        this.api.listAll<Generic>('/generic-solutions'),this.api.listAll<Product>('/products'),
        this.api.listAll<Taxon>('/systems'),this.api.listAll<Taxon>('/subsystems')]);
      this.systems.set(systems);this.subsystems.set(subsystems);
      const choices:Choice[]=[
        ...generics.map(x=>({subsystem:x.subsystem_id,key:`g:${x.id}` as SolutionKey,name:x.name_es,code:x.code,kind:'Genérica' as const})),
        ...products.map(x=>({subsystem:x.subsystem_id,key:`p:${x.id}` as SolutionKey,name:x.published?.name_es||x.code,code:x.code,kind:'Comercial' as const}))];
      this.allChoices.set(choices.sort((a,b)=>a.name.localeCompare(b.name,'es')));
      this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroy)).subscribe(params=>{
        const raw=params.get('ids')||'';
        const ids=normalizeComparisonIds(raw.split(','));
        if(raw)this.comparison.restore(ids.join(','));
        const selected=this.comparison.items().map(key=>this.allChoices().find(item=>item.key===key));
        const requestedSub=params.get('subsystem')||selected[0]?.subsystem||'';
        const sub=this.subsystems().find(item=>item.id===requestedSub);
        const system=params.get('system')||sub?.system_id||'';
        if(selected.some(item=>!item||item.subsystem!==requestedSub)||sub&&sub.system_id!==system){
          this.comparison.clear();this.notice.set('Selecciona dos soluciones publicadas del mismo sistema y subsistema.');
        }
        this.system.set(this.systems().some(item=>item.id===system)?system:'');
        this.subsystem.set(sub?.system_id===this.system()?requestedSub:'');
        if(raw&&(raw!==this.comparison.toQuery()||!params.get('system')||!params.get('subsystem')))this.sync();
        else void this.compare();
      });
    }catch(e){this.error.set(problem(e))}
  }
  chooseSystem(value:string){
    this.system.set(value);this.subsystem.set('');this.comparison.clear();this.sync();
  }
  chooseSubsystem(value:string){
    this.subsystem.set(value);this.comparison.clear();this.sync();
  }
  select(index:number,value:string){
    this.notice.set('');
    if(!value){this.remove(index);return;}
    if(!this.choices().some(item=>item.key===value))return;
    if(!this.comparison.replace(index,value)){
      this.notice.set('Ya está seleccionada en la otra posición o el identificador es inválido.');return;
    }
    this.sync();
  }
  remove(index:number){this.comparison.clearSlot(index);this.sync()}
  swap(){this.comparison.swap();this.sync()}
  clear(){this.comparison.clear();this.sync()}
  private sync(){
    const wanted=this.comparison.items().length===2?this.comparison.toQuery():'';
    if((this.route.snapshot.queryParamMap.get('ids')||'')===wanted &&
       (this.route.snapshot.queryParamMap.get('system')||'')===this.system() &&
       (this.route.snapshot.queryParamMap.get('subsystem')||'')===this.subsystem()){
      void this.compare();return;
    }
    void this.router.navigate([],{relativeTo:this.route,queryParams:{ids:wanted||null,system:this.system()||null,subsystem:this.subsystem()||null},replaceUrl:true})
      .then(success=>{if(!success)void this.compare()});
    // The route subscription reloads on successful navigation.
  }
  async compare(){
    const seq=++this.sequence;
    const ids=this.comparison.items();
    this.result.set(null);this.error.set('');
    if(ids.length!==2||!this.subsystem()||!this.system()){this.loading.set(false);return;}
    this.loading.set(true);
    try{
      const reply=await this.api.get<ComparedResult>('/solutions/compare',{ids:ids.join(','),system_id:this.system(),subsystem_id:this.subsystem()});
      if(seq===this.sequence)this.result.set(reply);
    }catch(e){if(seq===this.sequence)this.error.set(problem(e))}
    finally{if(seq===this.sequence)this.loading.set(false)}
  }
  visibleRows(section:ComparisonSection){return this.onlyDifferences?section.rows.filter(row=>row.different):section.rows}
  async copyUrl(){
    if(this.comparison.items().length!==2)return;
    const tree=this.router.createUrlTree(['/comparar'],{queryParams:{ids:this.comparison.toQuery(),system:this.system(),subsystem:this.subsystem()}});
    const url=new URL(this.router.serializeUrl(tree),window.location.origin).href;
    try{await navigator.clipboard.writeText(url);this.notice.set('Enlace copiado.')}
    catch{this.notice.set('No se pudo acceder al portapapeles. Copia la dirección del navegador.');}
  }
}
