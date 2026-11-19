import {Component,inject,OnInit,signal} from '@angular/core';
import {Router,RouterLink} from '@angular/router';
import {FormsModule} from '@angular/forms';
import {ApiService,SessionService,Product,Taxon,ManufacturerNotification,problem} from '../core/api';
@Component({standalone:true,imports:[FormsModule,RouterLink],template:`<div class="container content portal-content"><div class="section-head"><div><span class="eyebrow">Portal del fabricante</span><h1>Mis productos</h1><p>Gestiona fichas técnicas y sigue su estado editorial.</p></div>
@if(session.role()==='MANUFACTURER'){<button class="button" (click)="creating.set(!creating())">{{creating()?'Cerrar formulario':'Nuevo producto'}}</button>}</div>
@if(session.role()!=='MANUFACTURER'){<p class="notice">Accede con una cuenta fabricante para gestionar tus productos. <a routerLink="/acceso">Iniciar sesión</a></p>}@else{
<div class="stats"><div><strong>{{items().length}}</strong><small>Productos totales</small></div><div><strong>{{drafts()}}</strong><small>Borradores</small></div><div><strong>{{submitted()}}</strong><small>En revisión</small></div><div><strong>{{published()}}</strong><small>Publicados</small></div></div>
@if(creating()){<form class="panel" (ngSubmit)="create()"><div class="section-head"><h2>Crear nuevo producto</h2></div><div class="form-grid"><label>Subsistema<select name="subsystem" [(ngModel)]="subsystem" required><option value="">Seleccionar clasificación</option>@for(x of subsystems();track x.id){<option [value]="x.id">{{x.code}} · {{x.name_es}}</option>}</select></label><label>Código técnico<input name="code" [(ngModel)]="code" required placeholder="PROD-001"></label><label>Nombre del producto<input name="name" [(ngModel)]="name" required placeholder="Descripción comercial"></label><label>Unidad funcional<input name="unit" [(ngModel)]="unit" required placeholder="m2"></label></div><button class="button" [disabled]="busy()||!subsystem||!name.trim()||!code.trim()||!unit.trim()">Crear borrador</button></form>}
@if(error()){<p class="error">{{error()}}</p>}
<section class="panel">
  <h2>Inventario de la empresa</h2>
  <div class="work-controls">
    <label>Buscar producto<input type="search" [(ngModel)]="query" placeholder="Nombre o código"></label>
    <label>Estado editorial<select [(ngModel)]="status"><option value="">Todos los estados</option>
      <option value="DRAFT">Borrador</option><option value="SUBMITTED">En revisión</option>
      <option value="APPROVED">Aprobada</option><option value="REJECTED">Rechazada</option>
    </select></label>
  </div>
  @if(loading()){<p role="status">Cargando inventario…</p>}
  @else{
    <div class="technical-scroll"><table class="work-table">
      <thead><tr><th scope="col">Producto</th><th scope="col">Revisión</th><th scope="col">Estado</th><th scope="col">Acción</th></tr></thead>
      <tbody>@for(p of filtered();track p.id){
        <tr><td><strong>{{p.revisions?.[0]?.name_es}}</strong><br><small>{{p.code}}</small></td>
          <td>#{{p.revisions?.[0]?.number}}</td><td><span class="tag">{{state(p)}}</span></td>
          <td><a [routerLink]="['/fabricante/producto',p.id]" [attr.aria-label]="'Gestionar '+p.revisions?.[0]?.name_es">Gestionar</a></td>
        </tr>
      }@empty{<tr><td colspan="4">Sin productos en esta selección.</td></tr>}</tbody>
    </table></div>
  }
</section>
<section class="panel"><h2>Notificaciones</h2>@for(n of notifications();track n.id){<div class="file-row"><span>{{n.event}} — {{n.message}}</span><button class="text-link" (click)="read(n.id)">{{n.read_at?'Leída':'Marcar leída'}}</button></div>}@if(!notifications().length){<p class="muted">Sin notificaciones.</p>}</section>}
</div>`})
export class DashboardComponent implements OnInit{api=inject(ApiService);session=inject(SessionService);router=inject(Router);
 items=signal<Product[]>([]);subsystems=signal<Taxon[]>([]);notifications=signal<ManufacturerNotification[]>([]);error=signal('');busy=signal(false);
 creating=signal(false);loading=signal(true);query='';status='';
 state(product:Product){
   const labels:Record<string,string>={DRAFT:'Borrador',SUBMITTED:'En revisión',APPROVED:'Aprobada',REJECTED:'Rechazada'};
   return labels[product.revisions?.[0]?.status||'']||'Sin revisión';
 }
 filtered(){
   const term=this.query.trim().toLocaleLowerCase('es');
   return this.items().filter(p=>(!this.status||p.revisions?.[0]?.status===this.status)
     && (p.code+' '+(p.revisions?.[0]?.name_es||'')).toLocaleLowerCase('es').includes(term));
 }
 subsystem='';code='';name='';unit='m2';drafts=()=>this.items().filter(p=>p.revisions?.[0]?.status==='DRAFT').length;
 submitted=()=>this.items().filter(p=>p.revisions?.[0]?.status==='SUBMITTED').length;
 published=()=>this.items().filter(p=>!!p.published_revision_id).length;
 async ngOnInit(){if(this.session.role()!=='MANUFACTURER'){await this.session.restore()}if(this.session.role()==='MANUFACTURER')this.load()}
 async load(){
   this.loading.set(true);
   const outcomes=await Promise.allSettled([
     this.api.listAll<Product>('/manufacturer/products').then(rows=>this.items.set(rows)),
     this.api.listAll<Taxon>('/subsystems').then(rows=>this.subsystems.set(rows)),
     this.api.list<ManufacturerNotification>('/manufacturer/notifications').then(rows=>this.notifications.set(rows))
   ]);
   this.error.set(outcomes.flatMap(result=>result.status==='rejected'?[problem(result.reason)]:[]).join(' · '));
   this.loading.set(false);
 }
 async create(){this.error.set('');this.busy.set(true);try{const p=await this.api.post<Product>('/manufacturer/products',{subsystem_id:this.subsystem,code:this.code,name_es:this.name,functional_unit:this.unit,technical_data:{properties:{}},generic_solution_ids:[]});await this.router.navigateByUrl('/fabricante/producto/'+p.id)}catch(e){this.error.set(problem(e))}finally{this.busy.set(false)}}
 async read(id:string){try{await this.api.patch('/notifications/'+id+'/read',{});this.load()}catch(e){this.error.set(problem(e))}}
}
