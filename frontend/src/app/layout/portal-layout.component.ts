import {Component,Input} from '@angular/core';
import {RouterLink,RouterLinkActive,RouterOutlet} from '@angular/router';
import {UiIcon,UiIconComponent} from '../core/ui-icon.component';

interface PortalGroup {
  label:string;
  links:{route:string;label:string;icon:UiIcon;exact?:boolean}[];
}

const ADMIN:PortalGroup[]=[
  {label:'Operación',links:[
    {route:'/admin',label:'Vista general',icon:'overview',exact:true},
    {route:'/admin/revisiones',label:'Revisión de productos',icon:'layers'},
    {route:'/admin/legado',label:'Publicación del catálogo METRA-DEMO',icon:'history'},
  ]},
  {label:'Catálogo y datos',links:[
    {route:'/admin/taxonomia',label:'Taxonomía y genéricas',icon:'grid'},
    {route:'/admin/fabricantes',label:'Fabricantes',icon:'team'},
    {route:'/admin/calidad',label:'Plantillas y calidad',icon:'document'},
    {route:'/admin/documentos',label:'Centro documental',icon:'document'},
    {route:'/admin/costes',label:'Bases de costes',icon:'costs'},
    {route:'/admin/auditoria',label:'Auditoría',icon:'table'},
  ]},
];
const MANUFACTURER:PortalGroup[]=[
  {label:'Gestión de producto',links:[
    {route:'/fabricante',label:'Inventario y tareas',icon:'grid',exact:true},
    {route:'/fabricante/perfil',label:'Perfil de empresa',icon:'team'},
  ]},
];

@Component({selector:'app-portal-layout',standalone:true,imports:[RouterLink,RouterLinkActive,RouterOutlet,UiIconComponent],template:`
<div class="workspace-layout">
  <aside class="workspace-sidebar">
    <div class="workspace-identity"><span class="identity-symbol"><app-ui-icon [name]="kind==='admin'?'overview':'cube'"/></span>
      <div><span class="workspace-overline">Espacio de trabajo</span><strong>{{kind==='admin'?'Administración':'Fabricante'}}</strong></div>
    </div>
    <nav class="workspace-navigation" aria-label="Navegación del portal">
      @for(group of groups();track group.label){
        <div class="workspace-nav-group">
          <p class="workspace-menu-title">{{group.label}}</p>
          @for(link of group.links;track link.route){
            <a [routerLink]="link.route" [routerLinkActiveOptions]="{exact:!!link.exact}" routerLinkActive="current"
              ariaCurrentWhenActive="page" class="workspace-link"><app-ui-icon [name]="link.icon"/>{{link.label}}</a>
          }
        </div>
      }
    </nav>
    <div class="workspace-sidebar-bottom">
      <a routerLink="/catalogo" class="workspace-return">Volver al catálogo público</a>
    </div>
  </aside>
  <section class="workspace-main" aria-label="Contenido del portal"><router-outlet/></section>
</div>`})
export class PortalLayoutComponent {
  @Input() kind:'admin'|'manufacturer'='manufacturer';
  groups(){return this.kind==='admin'?ADMIN:MANUFACTURER}
}
