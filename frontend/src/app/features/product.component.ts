import {CanonicalPropertiesComponent} from './canonical-properties.component';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {Component,DestroyRef,inject,OnInit,signal} from '@angular/core';
import {ActivatedRoute,RouterLink} from '@angular/router';
import {ApiService,Product,problem} from '../core/api';
import {BudgetsComponent} from './budgets.component';
import {SolutionSection,SolutionShellComponent} from './solution-shell.component';
import {TechnicalPanelsComponent} from './technical-panels.component';
import {SolutionOverviewComponent} from './solution-overview.component';

@Component({standalone:true,imports:[CanonicalPropertiesComponent,RouterLink,SolutionShellComponent,TechnicalPanelsComponent,BudgetsComponent,SolutionOverviewComponent],template:`
<div class="container content solution-workbench">
  <a class="back" routerLink="/catalogo">← Volver al catálogo</a>
  @if(loading()){<p class="notice" role="status">Cargando ficha técnica…</p>}
  @if(error()){<p class="error" role="alert">{{error()}}</p>}
  @if(product();as p){@if(p.published;as revision){
    <div class="detail-head"><span class="tag">PRODUCTO · {{p.code}}</span><h1>{{revision.name_es}}</h1>
      <p>{{p.manufacturer?.name}} · {{revision.commercial_reference}} · {{revision.functional_unit}}</p>
    </div>
    <app-solution-shell [assets]="revision.assets" [revisionId]="revision.id" [bimStatus]="revision.bim_status"
      [section]="section()" (sectionChange)="section.set($event)">
      @if(section()==='Visión general'){
        <h2>Visión general</h2>
        <app-solution-overview [code]="p.code" [name]="revision.name_es" type="Comercial"
          [manufacturer]="p.manufacturer?.name||''" [unit]="revision.functional_unit"
          [documents]="revision.assets.length" [description]="revision.description||''"
          [canonical]="revision.canonical" [subsystem]="revision.canonical?.template?.code||''" [economic]="revision.economic_data" [environmental]="revision.environmental_data"/>
      }@else if(section()==='Historial'){
        <h2>Revisión publicada</h2><p>#{{revision.number}} · {{revision.status}}</p>
        <h3>Referencias genéricas</h3>
        @for(id of revision.generic_solution_ids;track id){<p><a [routerLink]="['/generica',id]">Ver referencia →</a></p>}
        @empty{<p class="muted">Sin referencias genéricas enlazadas.</p>}
      }@else if(section()==='Prestaciones' && revision.canonical){
        <app-canonical-properties [solution]="revision.canonical"/>
      }@else{
        <app-technical-panels [section]="section()" [technical]="revision.technical_data"
          [composition]="revision.technical_data?.composition || []" [assets]="revision.assets"
          [economic]="revision.economic_data" [environmental]="revision.environmental_data" [compositionScenario]="revision.technical_data?.composition_scenario"/>
      }
      @if(section()==='Economía'){<app-budgets [productId]="p.id"/>}
      @if(p.manufacturer?.public_email){<p><a [href]="'mailto:'+p.manufacturer?.public_email">Contactar fabricante ↗</a></p>}
    </app-solution-shell>
  }}
</div>`})
export class ProductComponent implements OnInit {
  private route=inject(ActivatedRoute);
  private api=inject(ApiService);
  private destroy=inject(DestroyRef);
  private loadNumber=0;
  product=signal<Product|null>(null);
  error=signal('');
  loading=signal(true);

  section=signal<SolutionSection>('Visión general');
  ngOnInit(){
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroy)).subscribe(params=>void this.load(params.get('id')||''));
  }
  async load(id:string){
    const request=++this.loadNumber;
    this.product.set(null);this.section.set('Visión general');this.error.set('');this.loading.set(true);
    try{
      const result=await this.api.get<Product>('/products/'+id);
      if(request===this.loadNumber){
        this.product.set(result);
      }
    }catch(e){if(request===this.loadNumber)this.error.set(problem(e))}
    finally{if(request===this.loadNumber)this.loading.set(false)}
  }
}
