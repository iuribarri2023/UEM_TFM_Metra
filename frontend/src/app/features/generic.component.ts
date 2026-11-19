import {CanonicalPropertiesComponent} from './canonical-properties.component';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {Component,DestroyRef,inject,OnInit,signal} from '@angular/core';
import {ActivatedRoute,RouterLink} from '@angular/router';
import {ApiService,Generic,problem} from '../core/api';
import {SolutionSection,SolutionShellComponent} from './solution-shell.component';
import {TechnicalPanelsComponent} from './technical-panels.component';
import {SolutionOverviewComponent} from './solution-overview.component';

@Component({standalone:true,imports:[CanonicalPropertiesComponent,RouterLink,SolutionShellComponent,TechnicalPanelsComponent,SolutionOverviewComponent],template:`
<div class="container content solution-workbench">
  <a class="back" routerLink="/catalogo">← Volver al catálogo</a>
  @if(loading()){<p class="notice" role="status">Cargando ficha técnica…</p>}
  @if(error()){<p class="error" role="alert">{{error()}}</p>}
  @if(item();as s){
    <div class="detail-head"><span class="tag secondary">REFERENCIA GENÉRICA · {{s.code}}</span><h1>{{s.name_es}}</h1></div>
    <app-solution-shell [assets]="s.assets" [bimStatus]="s.bim_status" [section]="section()" (sectionChange)="section.set($event)">
      @if(section()==='Visión general'){
        <h2>Visión general</h2>
        <app-solution-overview [code]="s.code" [name]="s.name_es" type="Genérica"
          [unit]="s.technical_data?.functional_unit||''" [documents]="s.assets.length"
          [description]="s.technical_data?.description||''" [canonical]="s.canonical" [subsystem]="s.canonical?.template?.code||''" [economic]="s.economic_data" [environmental]="s.environmental_data"/>
      }@else if(section()==='Historial'){
        <h2>Historial</h2><p>Estado actual · {{s.status}}</p>
        <p class="muted">Esta referencia no dispone de un historial de revisiones públicas.</p>
      }@else if(section()==='Prestaciones' && s.canonical){
        <app-canonical-properties [solution]="s.canonical"/>
      }@else{
        <app-technical-panels [section]="section()" [technical]="s.technical_data"
          [composition]="s.composition?.length?s.composition:s.slots" [assets]="s.assets"
          [economic]="s.economic_data" [environmental]="s.environmental_data" [compositionScenario]="s.technical_data?.composition_scenario"/>
      }
    </app-solution-shell>
  }
</div>`})
export class GenericComponent implements OnInit {
  private api=inject(ApiService);
  private destroy=inject(DestroyRef);
  private loadNumber=0;
  private route=inject(ActivatedRoute);
  item=signal<Generic|null>(null);
  error=signal('');
  loading=signal(true);

  section=signal<SolutionSection>('Visión general');
  ngOnInit(){
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroy)).subscribe(params=>void this.load(params.get('id')||''));
  }
  async load(id:string){
    const request=++this.loadNumber;
    this.item.set(null);this.section.set('Visión general');this.error.set('');this.loading.set(true);
    try{
      const result=await this.api.get<Generic>('/generic-solutions/'+id);
      if(request===this.loadNumber){
        this.item.set(result);
      }
    }catch(e){if(request===this.loadNumber)this.error.set(problem(e))}
    finally{if(request===this.loadNumber)this.loading.set(false)}
  }
}
