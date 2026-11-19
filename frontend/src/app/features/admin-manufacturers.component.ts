import {Component,inject,OnInit,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {ApiService,problem} from '../core/api';

interface Organization{id:string;code:string;name:string;status:string}

@Component({standalone:true,imports:[FormsModule],template:`
<div class="container content portal-content">
  <div class="portal-page-title"><span class="eyebrow">ADMINISTRACIÓN / ORGANIZACIONES</span><h1>Fabricantes</h1>
    <p>Vincula una cuenta a una empresa existente tras verificar su representación.</p>
  </div>
  @if(error()){<p class="error" role="alert">{{error()}}</p>}
  <form class="panel form-grid" (ngSubmit)="invite()">
    <label>Organización<select name="org" [(ngModel)]="organization" required (ngModelChange)="link.set('')">
      <option value="">Seleccionar</option>
      @for(org of organizations();track org.id){<option [value]="org.id" [disabled]="org.status!=='ACTIVE'">{{org.name}} · {{org.code}}</option>}
    </select></label>
    <label>Correo electrónico<input name="email" type="email" [(ngModel)]="email" required></label>
    <label>Evidencia de representación<textarea name="evidence" [(ngModel)]="evidence" minlength="10" maxlength="2000" required></textarea></label>
    <div><button class="button" [disabled]="busy()||!organization||!email||evidence.trim().length<10">Crear invitación</button></div>
  </form>
  @if(link()){<section class="panel"><label>Enlace de un solo uso (48 horas)<input readonly [value]="link()"></label></section>}
</div>`})
export class AdminManufacturersComponent implements OnInit {
  private api=inject(ApiService);
  organizations=signal<Organization[]>([]);link=signal('');error=signal('');busy=signal(false);
  organization='';email='';evidence='';
  async ngOnInit(){try{this.organizations.set(await this.api.listAll<Organization>('/admin/manufacturers'))}catch(e){this.error.set(problem(e))}}
  async invite(){
    this.error.set('');this.link.set('');this.busy.set(true);
    try{
      const result=await this.api.post<{invitation_token:string}>('/admin/manufacturers/'+this.organization+'/invitations',{email:this.email,evidence:this.evidence});
      this.link.set(location.origin+'/acceso?invitation='+encodeURIComponent(result.invitation_token));
    }catch(e){this.error.set(problem(e))}
    finally{this.busy.set(false)}
  }
}
