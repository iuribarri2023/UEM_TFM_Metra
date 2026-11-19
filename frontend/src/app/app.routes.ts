import {Routes} from '@angular/router';
export const APP_ROUTES:Routes=[
 {path:'',pathMatch:'full',loadComponent:()=>import('./features/home.component').then(m=>m.HomeComponent)},
 {path:'catalogo',loadComponent:()=>import('./features/catalogue.component').then(m=>m.CatalogueComponent)},
 {path:'producto/:id',loadComponent:()=>import('./features/product.component').then(m=>m.ProductComponent)},
 {path:'generica/:id',loadComponent:()=>import('./features/generic.component').then(m=>m.GenericComponent)},
 {path:'comparar',loadComponent:()=>import('./features/compare.component').then(m=>m.CompareComponent)},
 {path:'acceso',loadComponent:()=>import('./features/auth.component').then(m=>m.AuthComponent)},
 {path:'fabricante',loadComponent:()=>import('./layout/portal-layout.component').then(m=>m.PortalLayoutComponent),data:{kind:'manufacturer'},children:[
   {path:'',loadComponent:()=>import('./features/dashboard.component').then(m=>m.DashboardComponent)},
   {path:'producto/:id',loadComponent:()=>import('./features/editor.component').then(m=>m.EditorComponent)},
   {path:'perfil',loadComponent:()=>import('./features/profile.component').then(m=>m.ProfileComponent)}
 ]},
 {path:'admin',loadComponent:()=>import('./layout/admin-layout.component').then(m=>m.AdminLayoutComponent),children:[
   {path:'',loadComponent:()=>import('./features/admin-overview.component').then(m=>m.AdminOverviewComponent)},
   {path:'legado',loadComponent:()=>import('./features/catalogue-publication.component').then(m=>m.AdminLegacyComponent)},
  {path:'ifc',loadComponent:()=>import('./features/admin-ifc.component').then(m=>m.AdminIfcComponent)},
   {path:'documentos',loadComponent:()=>import('./features/admin-documents.component').then(m=>m.AdminDocumentsComponent)},
   {path:'fabricantes',loadComponent:()=>import('./features/admin-manufacturers.component').then(m=>m.AdminManufacturersComponent)},
   {path:'costes',loadComponent:()=>import('./features/cost-databases.component').then(m=>m.CostDatabasesComponent)},
   {path:'calidad',loadComponent:()=>import('./features/admin-quality.component').then(m=>m.AdminQualityComponent)},
   {path:':section',loadComponent:()=>import('./features/admin.component').then(m=>m.AdminComponent)}
 ]},
 {path:'**',redirectTo:'catalogo'}
];
