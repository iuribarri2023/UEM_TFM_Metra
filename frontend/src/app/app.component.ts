import {Component,inject,OnInit} from '@angular/core';
import {Router,RouterLink,RouterLinkActive,RouterOutlet} from '@angular/router';
import {METRA} from './core/brand';
import {SessionService} from './core/api';
import {ArchitecturalGlyphComponent} from './core/architectural-glyph.component';
@Component({selector:'app-root',standalone:true,imports:[RouterOutlet,RouterLink,RouterLinkActive,ArchitecturalGlyphComponent],template:`
<a class="skip-link" href="#main">Saltar al contenido</a>
<header class="header modern-header"><div class="container header-inner">
  <a class="brand modern-brand" routerLink="/" aria-label="Inicio METRA"><span class="brand-mark"><app-architectural-glyph system="MOD"/></span><span class="brand-lettering"><strong>{{brand.name}}</strong></span></a>
  <nav aria-label="Navegación principal"><a routerLink="/" routerLinkActive="nav-active" [routerLinkActiveOptions]="{exact:true}">Inicio</a><a routerLink="/catalogo" routerLinkActive="nav-active">Catálogo técnico</a><a routerLink="/comparar" routerLinkActive="nav-active">Comparador</a><a routerLink="/" fragment="fabricantes" class="manufacturer-nav">Fabricantes</a>
  @if(session.role()==='MANUFACTURER'){<a routerLink="/fabricante" class="nav-portal-link">Mi portal ↗</a>}
  @if(session.role()==='ADMIN'){<a routerLink="/admin" class="nav-portal-link">Administración ↗</a>}
  @if(session.role()){<button class="button button-ghost" (click)="signout()">Cerrar sesión</button>}
  @else{<a class="button login-link" routerLink="/acceso">Iniciar sesión</a>}
  </nav></div></header>
<main id="main"><router-outlet/></main>
<footer class="footer metra-footer"><div class="container"><strong>{{brand.name}}</strong><span>{{brand.description}}</span><span>{{brand.motto}}</span></div></footer>`})
export class AppComponent implements OnInit{
 brand=METRA;
 session=inject(SessionService);router=inject(Router);
 ngOnInit(){this.session.restore()}
 async signout(){await this.session.logout();this.router.navigateByUrl('/')}
}
