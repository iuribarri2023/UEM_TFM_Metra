import {Component,inject,OnInit,signal} from '@angular/core';
import {RouterLink} from '@angular/router';
import {ApiService,SessionService,problem} from '../core/api';
interface Overview {systems:number;subsystems:number;archetypes:number;generic_total:number;generic_published:number;generic_draft:number;commercial_total:number;commercial_public:number;legacy_quarantined:number;manufacturers:number;ifc_assets:number;pending_reviews:number}
@Component({standalone:true,imports:[RouterLink],template:`<div class="container content portal-content">
  <div class="portal-page-title"><span class="eyebrow">CENTRO DE CONTROL / ADMINISTRACIÓN</span><h1>Gobierno del catálogo</h1><p>Supervisión editorial y técnica del ciclo de vida de las soluciones.</p></div>
  @if(session.role()!=='ADMIN'){<p class="notice">Inicia sesión como administrador para consultar esta sección. <a routerLink="/acceso">Acceso</a></p>}
  @else{
   @if(error()){<p class="error" role="alert">{{error()}}</p>}
   @if(info();as v){
     <div class="portal-metric-grid">
       <div class="portal-metric"><span>SOLUCIONES GENÉRICAS</span><strong>{{v.generic_total}}</strong><small>{{v.generic_published}} publicadas · {{v.generic_draft}} en borrador</small></div>
       <div class="portal-metric"><span>PRODUCTOS COMERCIALES</span><strong>{{v.commercial_total}}</strong><small>{{v.commercial_public}} con publicación vigente</small></div>
       <div class="portal-metric"><span>MODELOS IFC INCORPORADOS</span><strong>{{v.ifc_assets}}</strong><small>Activos almacenados y trazados</small></div>
       <div class="portal-metric"><span>REVISIONES EN COLA</span><strong>{{v.pending_reviews}}</strong><small>Pendientes de decisión administrativa</small></div>
     </div>
     <div class="portal-two-col"><section class="panel"><span class="eyebrow">FLUJO DE TRABAJO</span><h2>Operaciones principales</h2><div class="portal-action-row"><div><strong>Validación de revisiones</strong><p>Examinar propuestas de fabricante y decidir su publicación.</p></div><a class="button button-light" routerLink="/admin/revisiones">Abrir cola ↗</a></div><div class="portal-action-row"><div><strong>Taxonomía y referencias técnicas</strong><p>{{v.systems}} sistemas · {{v.subsystems}} subsistemas · {{v.archetypes}} arquetipos.</p></div><a class="button button-light" routerLink="/admin/taxonomia">Gestionar ↗</a></div><div class="portal-action-row"><div><strong>Registros históricos del catálogo</strong><p>{{v.legacy_quarantined}} productos comerciales apartados hasta verificar derechos.</p></div><a class="button button-light" routerLink="/admin/legado">Explorar catálogo ↗</a></div></section>
       <aside class="panel"><span class="eyebrow">INTEGRIDAD Y PROCEDENCIA</span><h2>Publicación bajo control</h2><p>Los modelos y datos históricos conservan su procedencia; importar no equivale a aprobar ni a autorizar su descarga pública.</p><div class="portal-status-row"><span>Genéricas publicadas</span><strong>{{v.generic_published}}</strong></div><div class="portal-status-row"><span>Productos comerciales visibles</span><strong>{{v.commercial_public}}</strong></div><div class="portal-status-row"><span>Fabricantes registrados / importados</span><strong>{{v.manufacturers}}</strong></div><a routerLink="/admin/auditoria">Consultar auditoría ↗</a></aside>
     </div>
   } @else{<p class="notice">Cargando información de gobierno del catálogo…</p>}
  }
</div>`})
export class AdminOverviewComponent implements OnInit{
 api=inject(ApiService);session=inject(SessionService);info=signal<Overview|null>(null);error=signal('');
 async ngOnInit(){try{if(!this.session.role())await this.session.restore();if(this.session.role()==='ADMIN')this.info.set(await this.api.get<Overview>('/admin/overview'))}catch(e){this.error.set(problem(e))}}
}
