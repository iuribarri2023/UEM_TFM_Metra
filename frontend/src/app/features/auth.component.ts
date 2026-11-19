import {Component,inject,signal} from '@angular/core';
import {FormBuilder,ReactiveFormsModule,Validators} from '@angular/forms';
import {Router,ActivatedRoute} from '@angular/router';
import {ApiService,SessionService,SessionTokens,problem} from '../core/api';
@Component({standalone:true,imports:[ReactiveFormsModule],template:`<div class="container content narrow"><span class="eyebrow">Espacio fabricantes</span><h1>{{invitation?'Aceptar invitación':mode()==='register'?'Crear organización':'Acceder'}}</h1>
<p>Administra productos constructivos, prestaciones técnicas y publicaciones desde tu área privada.</p><div class="panel">
@if(!invitation){<div class="tabs"><button type="button" [class.active]="mode()==='login'" (click)="mode.set('login')">Entrar</button><button type="button" [class.active]="mode()==='register'" (click)="mode.set('register')">Registrarse</button></div>}
<form [formGroup]="form" (ngSubmit)="submit()">@if(mode()==='register' && !invitation){<label>Nombre de empresa<input formControlName="manufacturer_name" autocomplete="organization"></label>}
<label>Correo electrónico<input type="email" formControlName="email" autocomplete="email"></label>
<label>Contraseña (mínimo 12 caracteres)<input type="password" formControlName="password" autocomplete="current-password"></label>
@if(error()){<p class="error" role="alert">{{error()}}</p>}<button class="button full" type="submit" [disabled]="busy()">{{busy()?'Procesando…':'Continuar'}}</button></form>
<p class="muted small">El registro crea una empresa nueva. La incorporación a una empresa existente requiere una invitación de un solo uso.</p></div></div>`})
export class AuthComponent{api=inject(ApiService);session=inject(SessionService);router=inject(Router);route=inject(ActivatedRoute);fb=inject(FormBuilder);
 mode=signal<'login'|'register'>('login');invitation=this.route.snapshot.queryParamMap.get('invitation');error=signal('');busy=signal(false);
 form=this.fb.nonNullable.group({manufacturer_name:[''],email:['',[Validators.required,Validators.email]],password:['',[Validators.required,Validators.minLength(12)]]});
 async submit(){
  if(this.busy())return;
  this.error.set('');
  if(this.form.invalid){this.form.markAllAsTouched();this.error.set('Revisa el correo y la contraseña.');return;}
  if(!this.invitation&&this.mode()==='register'&&!this.form.controls.manufacturer_name.value.trim()){
    this.error.set('Introduce el nombre de la empresa.');return;
  }
  this.busy.set(true);try{
  const value=this.form.getRawValue();let path='/auth/login';let payload:{email:string;password:string;token?:string;manufacturer_name?:string}={email:value.email,password:value.password};
  if(this.invitation){path='/auth/accept-invitation';payload.token=this.invitation}
  else if(this.mode()==='register'){path='/auth/register';payload.manufacturer_name=value.manufacturer_name}
  const response=await this.api.post<SessionTokens>(path,payload);this.session.setSession(response);await this.session.me();
  await this.router.navigateByUrl(this.session.role()==='ADMIN'?'/admin':'/fabricante');
 }catch(e){this.error.set(problem(e))}finally{this.busy.set(false)}}
}
