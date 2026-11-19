import {Component,inject,OnInit,signal} from '@angular/core';
import {RouterLink} from '@angular/router';
import {FormsModule} from '@angular/forms';
import {ApiService,ManufacturerProfile,Invitation,problem} from '../core/api';
@Component({standalone:true,imports:[FormsModule,RouterLink],template:`<div class="container content narrow"><a class="back" routerLink="/fabricante">← Volver</a><span class="eyebrow">Mi organización</span><h1>Datos del fabricante</h1><div class="panel">
<label>Nombre<input [(ngModel)]="profile.name"></label><label>Descripción<textarea [(ngModel)]="profile.description"></textarea></label>
<label>Web corporativa (HTTPS)<input [(ngModel)]="profile.website"></label><label>Email público de contacto<input type="email" [(ngModel)]="profile.public_email"></label>
<label class="inline-check"><input type="checkbox" [(ngModel)]="profile.contact_public"> Autorizar contacto público</label><button class="button" (click)="save()">Guardar perfil</button>
@if(message()){<p class="notice">{{message()}}</p>}@if(error()){<p class="error">{{error()}}</p>}
</div><div class="panel"><h2>Invitar colaborador</h2><p>Invitación individual, de un solo uso y válida 48 horas. Comparte el enlace por un canal privado.</p><label>Correo del invitado<input type="email" [(ngModel)]="inviteEmail"></label><button class="button button-light" (click)="invite()">Generar invitación</button>
@if(invitation()){<label>Enlace de invitación<input readonly [value]="invitation()" (focus)="selectInvitation($event)"></label>}</div></div>`})
export class ProfileComponent implements OnInit{api=inject(ApiService);profile:ManufacturerProfile={name:'',description:'',website:null,public_email:null,contact_public:false};message=signal('');error=signal('');inviteEmail='';invitation=signal('');
 async ngOnInit(){try{this.profile=await this.api.get<ManufacturerProfile>('/manufacturer/profile')}catch(e){this.error.set(problem(e))}}
 async save(){try{await this.api.patch('/manufacturer/profile',this.profile);this.message.set('Perfil actualizado')}catch(e){this.error.set(problem(e))}}
 selectInvitation(event:FocusEvent){if(event.target instanceof HTMLInputElement)event.target.select()};
 async invite(){try{const x=await this.api.post<Invitation>('/manufacturer/invitations',{email:this.inviteEmail});this.invitation.set(location.origin+'/acceso?invitation='+encodeURIComponent(x.invitation_token))}catch(e){this.error.set(problem(e))}}
}
