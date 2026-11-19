import {SubsystemTemplate,TemplateHighlight} from '../core/canonical';
import {Component,DestroyRef,inject,OnInit,signal,computed} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {ActivatedRoute,ParamMap,Router,RouterLink} from '@angular/router';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {UiIconComponent} from '../core/ui-icon.component';
import {ArchitecturalGlyphComponent} from '../core/architectural-glyph.component';
import {DocumentGlyphComponent} from '../core/document-glyph.component';
import {humanizeTechnicalKey,esNumber} from '../core/technical-terminology';
import {ApiService,Asset,Product,Generic,Taxon,problem} from '../core/api';
import {ComparisonStateService,SolutionKey,MAX_COMPARISON_ITEMS,normalizeComparisonKey} from '../core/comparison-state.service';

type CatalogueTab='generics'|'products';
type PublicationCounts=Record<CatalogueTab,Record<string,number>>;

/** Public, published-only technical discovery. No private legacy data is exposed. */
@Component({standalone:true,imports:[FormsModule,RouterLink,UiIconComponent,ArchitecturalGlyphComponent,DocumentGlyphComponent],template:`
<div class="container catalog-shell catalogue-workbench">
  <header class="catalog-masthead">
    <div class="catalog-heading"><span class="eyebrow">Biblioteca constructiva</span><h1>Catálogo de soluciones</h1>
      <p>Encuentra referencias genéricas y productos de fabricantes por sistema constructivo.</p></div>
    <form class="catalog-search" (ngSubmit)="apply()">
      <label class="sr-only" for="search">Buscar soluciones</label>
      <input id="search" type="search" name="search" [(ngModel)]="q" placeholder="Nombre o código">
      <button class="button" type="submit">Buscar</button>
    </form>
  </header>
  <div class="catalogue-layout modern-catalogue">
    <details class="filters taxonomy-panel" [open]="desktop()">
      <summary class="taxonomy-panel-heading"><strong>Clasificación constructiva</strong></summary>
      <nav aria-label="Árbol de clasificación">
        <button class="taxonomy-all" [class.selected]="!system" [attr.aria-pressed]="!system" (click)="chooseSystem('')">
          Todos los sistemas <span>{{allCount() ?? '—'}}</span>
        </button>
        @for(s of systems();track s.id){
          <div class="taxonomy-group">
            <button class="taxonomy-parent" [class.selected]="system===s.id" [attr.aria-expanded]="system===s.id" (click)="chooseSystem(s.id)">
              <app-architectural-glyph [system]="s.code"/><span>{{s.name_es}}</span><small>{{systemCount(s.id) ?? '—'}}</small>
            </button>
            @if(system===s.id){
              <div class="taxonomy-children">
                @for(sub of systemSubs(s.id);track sub.id){
                  <button class="taxonomy-child" [class.selected]="subsystem===sub.id" [attr.aria-expanded]="subsystem===sub.id" (click)="chooseSubsystem(sub.id)">
                    {{sub.name_es}} <small>{{subCount(sub.id) ?? '—'}}</small>
                  </button>
                  @if(subsystem===sub.id){
                    <div class="taxonomy-archetypes">
                      @for(a of subArches(sub.id);track a.id){
                        <button [class.selected]="archetype===a.id" [attr.aria-pressed]="archetype===a.id" (click)="chooseArchetype(a.id)">{{a.name_es}}</button>
                      }
                    </div>
                  }
                }
              </div>
            }
          </div>
        }
      </nav>
      <p class="taxonomy-help">Los recuentos muestran las publicaciones del catálogo por clasificación.</p>
    </details>
    <section class="results" aria-label="Resultados del catálogo" [attr.aria-busy]="loading()">
      <div class="catalog-toolbar">
        <div class="tabs" role="group" aria-label="Tipo de solución">
          <button [class.active]="tab()==='generics'" [attr.aria-pressed]="tab()==='generics'" (click)="chooseTab('generics')">Referencias genéricas <span>{{totals().generics ?? '—'}}</span></button>
          <button [class.active]="tab()==='products'" [attr.aria-pressed]="tab()==='products'" (click)="chooseTab('products')">Productos comerciales <span>{{totals().products ?? '—'}}</span></button>
        </div>
        <button class="button button-ghost" [attr.aria-pressed]="dense" (click)="dense=!dense;apply(page)">Vista de lista</button>
      </div>
      <details class="filter-drawer" [open]="desktop()">
        <summary>Filtros de búsqueda</summary>
        <div class="catalog-controls">
          <div class="format-options" role="group" aria-label="Documentos requeridos">
            @for(type of formats;track type){
              <button class="filter-pill" [attr.aria-pressed]="documents.has(type)" (click)="toggleDocument(type)">{{type}}</button>
            }
          </div>
          <form (ngSubmit)="apply()" class="unit-filter">
            <label>Unidad funcional<input name="unit" [(ngModel)]="unit" placeholder="p. ej. m2" maxlength="24"></label>
            <button class="button button-ghost" type="submit">Aplicar</button>
          </form>
          @if(filterTemplate();as template){
            <form class="unit-filter" (ngSubmit)="apply()">
              <label>Propiedad técnica<select name="property" [(ngModel)]="property">
                <option value="">Sin filtro de propiedad</option>
                @for(field of template.fields;track field.code){@if(field.type==='number'){
                  <option [value]="field.code">{{field.name_es||field.label||field.code}} · {{field.unit}}</option>
                }}
              </select></label>
              @if(property){
                <label>Mínimo<input type="number" step="any" name="minimum" [(ngModel)]="minimum"></label>
                <label>Máximo<input type="number" step="any" name="maximum" [(ngModel)]="maximum"></label>
              }
              <button type="submit" class="button button-ghost">Aplicar propiedad</button>
            </form>
          }
          @if(tab()==='products'){
            <label>Fabricante<select [(ngModel)]="manufacturer" (ngModelChange)="apply()"><option value="">Todos</option>
              @for(org of organizations();track org.id){<option [value]="org.id">{{org.name}}</option>}
            </select></label>
          }
          <button class="text-link" (click)="reset()">Limpiar filtros</button>
        </div>
      </details>
      <div class="results-summary">
        <p aria-live="polite">
          @if(!loading()&&total()!==null){<strong>{{total()}}</strong> resultados · {{scopeName()}}
            @if(total()){<span> · {{rangeStart()}}–{{rangeEnd()}}</span>}
          }
        </p>
        <label>Ordenar<select [(ngModel)]="sort" (ngModelChange)="apply()"><option value="name">Nombre A–Z</option><option value="code">Código técnico</option></select></label>
      </div>
      @if(taxonomyNotice()){<p class="notice" role="status">{{taxonomyNotice()}}</p>}
      @if(error()){<p class="error" role="alert">{{error()}} <button class="text-link" (click)="reload()">Reintentar</button></p>}
      @if(loading()){
        <p class="sr-only" role="status">Cargando fichas técnicas…</p>
        <div class="catalog-skeleton" aria-hidden="true"><div></div><div></div><div></div></div>
      }@else{
        @if(dense&&cards().length){
          <div class="catalog-table technical-scroll">
            <table class="work-table">
              <thead><tr><th scope="col">Ficha y código</th><th scope="col">Clasificación</th>
                @if(tab()==='products'){<th scope="col">Fabricante</th>}
                <th scope="col">Disponibilidad</th><th scope="col">Prestaciones</th>
                <th scope="col">Comparación</th>
              </tr></thead>
              <tbody>@for(card of cards();track card.id){
                <tr><th scope="row"><a [routerLink]="card.route">{{card.name}}</a><small>{{card.code}}</small></th>
                  <td>{{subsystemName(card.subsystem)||'—'}}</td>
                  @if(tab()==='products'){<td>{{card.maker||'—'}}</td>}
                  <td><div class="document-badges">
                    @for(doc of card.documents;track doc.type){<span [class.available]="doc.available"><app-document-glyph [format]="doc.type"/>{{doc.type}} · {{doc.label}}</span>}
                  </div></td>
                  <td>@for(row of card.properties;track row.label){<div>{{row.label}} <strong>{{row.value}}</strong></div>}@empty{—}</td>
                  <td><button type="button" class="text-link" [attr.aria-pressed]="compareIds().includes(card.compareKey)" (click)="toggleCompare(card.compareKey)">
                    {{compareIds().includes(card.compareKey)?'Retirar':'Comparar'}}</button></td>
                </tr>
              }</tbody>
            </table>
          </div>
        }@else{
          <div class="card-grid catalog-cards">
            @for(card of cards();track card.id){
              <article class="product-card technical-card catalog-specimen">
                <div class="catalog-media">
                  @if(card.thumbnail&&!failedThumbnails().has(card.thumbnail)){
                    <img [src]="'/api/v1/documents/'+card.thumbnail+'/thumbnail'" alt="Vista axonométrica del modelo IFC"
                      loading="lazy" decoding="async" width="320" height="176" (error)="thumbnailFailed(card.thumbnail)">
                  }@else{
                    <div class="catalog-media-fallback"><app-architectural-glyph [system]="subsystemCode(card.subsystem)||card.code"/><span>Ilustración esquemática · sin miniatura IFC</span></div>
                  }
                  <span class="tag catalog-kind">{{card.maker?'Producto':'Genérica'}}</span>
                </div>
                <div class="catalog-specimen-content">
                  <span class="card-code">{{card.code}}</span>
                  <h3><a [routerLink]="card.route">{{card.name}}</a></h3>
                  <p class="technical-description">{{card.maker||subsystemName(card.subsystem)||'Referencia técnica'}}</p>
                  @if(card.maker){<p class="small muted">{{subsystemName(card.subsystem)}} @if(card.unit){· {{card.unit}}}</p>}
                  <div class="card-properties">@for(row of card.properties;track row.label){<span>{{row.label}} <strong>{{row.value}}</strong></span>}</div>
                  <div class="document-badges">@for(doc of card.documents;track doc.type){
                    <span [class.available]="doc.available"><app-document-glyph [format]="doc.type"/>{{doc.type}} · {{doc.label}}</span>
                  }</div>
                  <div class="card-bottom">
                    <button type="button" class="text-link" [attr.aria-pressed]="compareIds().includes(card.compareKey)"
                        (click)="toggleCompare(card.compareKey)">
                        {{compareIds().includes(card.compareKey)?'Retirar de comparación':'Comparar'}}</button>
                    <a [routerLink]="card.route">Ver ficha <app-ui-icon name="arrow"/></a>
                  </div>
                </div>
              </article>
            }
          </div>
        }
        @if(!error()&&total()===0){
          <div class="catalog-empty"><div class="empty-symbol">◇</div><h3>Sin publicaciones en esta selección</h3><p>Prueba otro término o elimina filtros para ampliar la búsqueda.</p><button class="button button-ghost" (click)="reset()">Limpiar filtros</button></div>
        }
        @if(pageCount()>1){
          <nav class="pagination" aria-label="Paginación del catálogo">
            <button class="button button-ghost" [disabled]="page<=1" (click)="apply(page-1)">Anterior</button>
            <span>Página {{page}} de {{pageCount()}}</span>
            <button class="button button-ghost" [disabled]="page>=pageCount()" (click)="apply(page+1)">Siguiente</button>
          </nav>
        }
      }
      @if(compareIds().length){
        <div class="compare-tray">
          <span>{{compareIds().length}} de {{maxCompare}} soluciones para comparar</span>
          <button class="text-link" (click)="comparison.clear();pendingCompare.set('')">Vaciar</button>
          @if(compareIds().length>=2){
            <a class="button" [routerLink]="['/comparar']" [queryParams]="{ids:compareIds().join(',')}">Abrir comparador</a>
          }
        </div>
      }
      @if(compareNotice()){<p class="notice" role="status">{{compareNotice()}}</p>}
      @if(pendingCompare()){
        <div class="compare-replacement panel" role="group" aria-label="Sustituir una solución de comparación">
          <p>Ya hay dos soluciones. Elige a cuál sustituir; no se cambiará ninguna sin tu decisión.</p>
          <button type="button" class="button button-ghost" (click)="replaceCompare(0)">Sustituir A</button>
          <button type="button" class="button button-ghost" (click)="replaceCompare(1)">Sustituir B</button>
          <button type="button" class="text-link" (click)="pendingCompare.set('');compareNotice.set('')">Cancelar</button>
        </div>
      }
    </section>
  </div>
</div>`})
export class CatalogueComponent implements OnInit {
  failedThumbnails=signal<Set<string>>(new Set());
  thumbnailFailed(id:string){this.failedThumbnails.update(items=>new Set([...items,id]))}
  cards=computed(()=>this.tab()==='generics'
    ?this.generics().map(item=>this.card(item.id,item.code,item.name_es,item.subsystem_id,['/generica',item.id],
      item.assets,item.bim_status,item.technical_data,undefined,undefined,item.template_highlights))
    :this.products().map(item=>this.card(item.id,item.code,item.published?.name_es||item.code,item.subsystem_id,
      ['/producto',item.id],item.published?.assets||[],item.published?.bim_status,item.published?.technical_data,
      item.manufacturer?.name,item.published?.functional_unit,item.published?.template_highlights)));
  private card(id:string,code:string,name:string,subsystem:string,route:string[],assets:Asset[],status?:string,
               technical?:unknown,maker?:string,unit?:string,highlights?:TemplateHighlight[]){
    const thumbnail=status==='VIEWABLE'&&assets.find(asset=>asset.file_type==='IFC'&&asset.public_view_allowed&&asset.thumbnail_available)?.id||'';
    const documents=this.formats.map(type=>{
      const available=type==='IFC'?status==='VIEWABLE':this.hasDocument(assets,type);
      return {type,available,label:type==='IFC'?this.bimLabel(status):available?'Disponible':'Sin archivo público'};
    });
    const compareKey:SolutionKey=this.tab()==='generics'?`g:${id}`:`p:${id}`;
    return {id,compareKey,code,name,subsystem,route,maker,unit,thumbnail,documents,properties:highlights?.map(x=>({label:x.label,value:String(x.value)+(x.unit==='unit'?'':' '+x.unit)}))??this.highlights(technical)};
  }
  bimLabel(status?:string){return ({NO_IFC:'Sin IFC',PRIVATE:'Asociado · sin vista pública',PROCESSING:'En procesamiento',INVALID:'Inválido',MISSING:'Asociado · archivo ausente',CORRUPT:'Integridad fallida',VIEWABLE:'Asociado · visible'} as Record<string,string>)[status||'']||'Sin información'}
  private api=inject(ApiService);
  private route=inject(ActivatedRoute);
  private router=inject(Router);
  private destroy=inject(DestroyRef);
  readonly pageSize=12;
  private readonly viewport=window.matchMedia('(min-width: 861px)');
  readonly desktop=signal(this.viewport.matches);
  readonly formats=['IFC','BC3','EPD'];
  tab=signal<CatalogueTab>('generics');
  filterTemplate=signal<SubsystemTemplate|null>(null);
  property='';minimum:number|null=null;maximum:number|null=null;
  q='';system='';subsystem='';archetype='';sort='name';manufacturer='';unit='';dense=false;page=1;
  documents=new Set<string>();
  systems=signal<Taxon[]>([]);subsystems=signal<Taxon[]>([]);archetypes=signal<Taxon[]>([]);
  organizations=signal<{id:string;name:string}[]>([]);
  products=signal<Product[]>([]);generics=signal<Generic[]>([]);
  loading=signal(true);error=signal('');taxonomyNotice=signal('');
  counts=signal<PublicationCounts|null>(null);
  totals=signal<Record<CatalogueTab,number|null>>({products:null,generics:null});
  readonly comparison=inject(ComparisonStateService);
  readonly compareIds=this.comparison.items;
  readonly maxCompare=MAX_COMPARISON_ITEMS;
  pendingCompare=signal<SolutionKey|''>('');
  compareNotice=signal('');
  private loadId=0;

  ngOnInit(){
    const viewportChanged=(event:MediaQueryListEvent)=>this.desktop.set(event.matches);
    this.viewport.addEventListener('change',viewportChanged);
    this.destroy.onDestroy(()=>this.viewport.removeEventListener('change',viewportChanged));
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroy)).subscribe(params=>{
      this.readFilters(params);
      void this.loadFilterTemplate();
      void this.reload(!params.has('view'));
    });
    void this.loadTaxonomy();
  }

  async loadTaxonomy(){
    const outcomes=await Promise.allSettled([
      this.api.listAll<Taxon>('/systems').then(rows=>this.systems.set(rows)),
      this.api.listAll<Taxon>('/subsystems').then(rows=>{this.subsystems.set(rows);return this.loadFilterTemplate()}),
      this.api.listAll<Taxon>('/archetypes').then(rows=>this.archetypes.set(rows)),
      this.api.listAll<{id:string;name:string}>('/manufacturers',{scope:'catalogue'}).then(rows=>this.organizations.set(rows)),
      this.api.get<PublicationCounts>('/catalogue/counts').then(counts=>this.counts.set(counts))
    ]);
    if(outcomes.some(result=>result.status==='rejected'))this.taxonomyNotice.set('Parte de la clasificación o de sus recuentos no está disponible.');
  }

  private readFilters(params:ParamMap){
    const id=(key:string)=>{
      const value=params.get(key)||'';
      return /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(value)?value:'';
    };
    this.tab.set(params.get('view')==='products'?'products':'generics');
    this.q=(params.get('q')||'').slice(0,150);
    this.unit=(params.get('unit')||'').slice(0,24);
    this.system=id('system');this.subsystem=id('subsystem');this.archetype=id('archetype');
    this.manufacturer=id('manufacturer');
    this.property=(params.get('property')||'').slice(0,100);
    this.minimum=params.has('minimum')?Number(params.get('minimum')):null;
    this.maximum=params.has('maximum')?Number(params.get('maximum')):null;
    this.sort=params.get('sort')==='code'?'code':'name';
    this.dense=params.get('layout')==='list';
    this.documents=new Set(this.formats.filter(format=>params.get(format.toLowerCase())==='1'));
    const page=Number(params.get('page')||'1');
    this.page=Number.isInteger(page)&&page>=1&&page<=10000?page:1;
  }

  apply(page=1,replaceUrl=false){
    void this.router.navigate([], {relativeTo:this.route,replaceUrl,queryParams:{
      view:this.tab(),q:this.q.trim()||null,unit:this.unit.trim()||null,
      system:this.system||null,subsystem:this.subsystem||null,archetype:this.archetype||null,
      property:this.property||null,minimum:this.property?this.minimum:null,maximum:this.property?this.maximum:null,
      manufacturer:this.manufacturer||null,sort:this.sort==='code'?'code':null,
      layout:this.dense?'list':null,page:page>1?page:null,
      ...Object.fromEntries(this.formats.map(format=>[format.toLowerCase(),this.documents.has(format)?'1':null]))
    }});
  }

  chooseTab(tab:CatalogueTab){if(tab!==this.tab()){this.tab.set(tab);this.apply()}}
  chooseSystem(id:string){this.system=this.system===id?'':id;this.subsystem='';this.archetype='';this.clearProperty();this.apply()}
  chooseSubsystem(id:string){this.subsystem=this.subsystem===id?'':id;this.archetype='';this.clearProperty();this.apply()}
  chooseArchetype(id:string){this.archetype=this.archetype===id?'':id;this.apply()}
  toggleDocument(type:string){if(this.documents.has(type))this.documents.delete(type);else this.documents.add(type);this.apply()}
  toggleCompare(input:string){
    const key=normalizeComparisonKey(input);
    if(!key)return;
    if(this.compareIds().includes(key)){
      this.comparison.remove(key);this.pendingCompare.set('');this.compareNotice.set('');return;
    }
    const outcome=this.comparison.add(key);
    if(outcome==='full'){
      this.pendingCompare.set(key);
      this.compareNotice.set('Máximo dos soluciones. Puedes sustituir A o B sin perder la otra.');
    }else if(outcome==='added'){
      this.pendingCompare.set('');this.compareNotice.set('');
    }
  }
  replaceCompare(index:number){
    if(this.pendingCompare()&&this.comparison.replace(index,this.pendingCompare())){
      this.pendingCompare.set('');this.compareNotice.set('Solución sustituida.');
    }
  }
  reset(){this.system='';this.subsystem='';this.archetype='';this.q='';this.manufacturer='';this.unit='';this.clearProperty();this.documents.clear();this.apply()}

  systemSubs(id:string){return this.subsystems().filter(s=>s.system_id===id)}
  subArches(id:string){return this.archetypes().filter(a=>a.subsystem_id===id)}
  subsystemCode(id:string){return this.subsystems().find(item=>item.id===id)?.code||''}
  private clearProperty(){this.property='';this.minimum=null;this.maximum=null}
  private async loadFilterTemplate(){
    const sub=this.subsystem;
    const code=this.subsystemCode(sub);
    if(!code){this.filterTemplate.set(null);return}
    try{
      const template=await this.api.get<SubsystemTemplate>('/data-templates/'+code);
      if(this.subsystem===sub)this.filterTemplate.set(template);
    }catch{if(this.subsystem===sub)this.filterTemplate.set(null)}
  }
  subsystemName(id:string){return this.subsystems().find(s=>s.id===id)?.name_es||''}
  subCount(id:string){const counts=this.counts();return counts?(counts[this.tab()][id]||0):null}
  systemCount(id:string){return this.counts()?this.systemSubs(id).reduce((n,sub)=>n+(this.subCount(sub.id)||0),0):null}
  allCount(){const counts=this.counts();return counts?Object.values(counts[this.tab()]).reduce((a,b)=>a+b,0):null}
  scopeName(){return this.subsystemName(this.subsystem)||this.systems().find(item=>item.id===this.system)?.name_es||'Catálogo público'}
  total(){return this.totals()[this.tab()]}
  pageCount(){return Math.min(10000,Math.ceil((this.total()||0)/this.pageSize))}
  rangeStart(){return (this.page-1)*this.pageSize+1}
  rangeEnd(){return Math.min(this.page*this.pageSize,this.total()||0)}
  hasDocument(assets:{file_type:string;processing_status:string}[]|undefined,type:string){
    return !!assets?.some(asset=>asset.file_type===type&&asset.processing_status==='VALID');
  }
 highlights(data:any){
   const entries=Object.entries(data?.technical_performance || data?.properties || {});
   return entries.flatMap(([label, raw])=>{
     const record=raw as {value?:unknown;unit?:string}|null;
     const value=record&&typeof record==='object'?record.value:raw;
     if(typeof value!=='number'&&typeof value!=='string')return [];
     return [{label:humanizeTechnicalKey(label),value:(typeof value==='number'?esNumber(value):String(value))+(record?.unit?' '+record.unit:'')}];
   }).slice(0,2);
 }

  async reload(chooseInitialTab=false){
    const run=++this.loadId;
    const currentTab=this.tab();
    this.loading.set(true);this.error.set('');this.products.set([]);this.generics.set([]);
    const params:Record<string,string|number>={q:this.q.trim(),sort:this.sort,template_summary:'1'};
    if(this.system)params['system_id']=this.system;
    if(this.subsystem)params['subsystem_id']=this.subsystem;
    if(this.subsystem&&this.property){
      params['property']=this.property;
      if(this.minimum!==null)params['minimum']=this.minimum;
      if(this.maximum!==null)params['maximum']=this.maximum;
    }
    if(this.archetype)params['archetype_id']=this.archetype;
    if(this.unit.trim())params['unit']=this.unit.trim();
    for(const type of this.documents)params[type.toLowerCase()]='1';
    const paging=(tab:CatalogueTab)=>({page:tab===currentTab?this.page:1,page_size:tab===currentTab?this.pageSize:1});
    const [products,generics]=await Promise.allSettled([
      this.api.page<Product>('/products',{...params,...paging('products'),...(this.manufacturer?{manufacturer_id:this.manufacturer}:{})}),
      this.api.page<Generic>('/generic-solutions',{...params,...paging('generics')})
    ]);
    if(run!==this.loadId)return;
    const totals={
      products:products.status==='fulfilled'?products.value.meta?.total??0:null,
      generics:generics.status==='fulfilled'?generics.value.meta?.total??0:null
    };
    this.totals.set(totals);
    if(chooseInitialTab&&totals.products&&totals.generics===0){
      this.tab.set('products');this.apply(1,true);return;
    }
    if(this.page>1&&totals[currentTab]!==null&&this.page>Math.max(1,this.pageCount())){
      this.apply(Math.max(1,this.pageCount()),true);return;
    }
    if(products.status==='fulfilled')this.products.set(products.value.data);
    if(generics.status==='fulfilled')this.generics.set(generics.value.data);
    const current=currentTab==='products'?products:generics;
    if(current.status==='rejected')this.error.set(problem(current.reason));
    this.loading.set(false);
  }
}
