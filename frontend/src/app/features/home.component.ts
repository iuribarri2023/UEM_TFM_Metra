import {Component,inject,OnInit,signal} from '@angular/core';
import {RouterLink} from '@angular/router';
import {ApiService,Generic,Product} from '../core/api';
import {ArchitecturalGlyphComponent} from '../core/architectural-glyph.component';

@Component({standalone:true,imports:[RouterLink,ArchitecturalGlyphComponent],styleUrl:'./home.component.css',template:`
<div class="metra-home">
  <section class="home-hero" aria-labelledby="home-title">
    <div class="container home-hero-grid">
      <div class="home-hero-copy">
        <span class="home-eyebrow"><span class="home-led"></span> Plataforma de información constructiva interoperable</span>
        <p class="home-edition">METRA / VISUAL EXPERIENCE 2026</p>
        <h1 id="home-title">Cada componente.<br><em>Todos sus datos.</em></h1>
        <p class="home-lede">La información constructiva, conectada. Modelos BIM, prestaciones, composición, economía y ambiente en un único lenguaje técnico.</p>
        <div class="home-actions"><a routerLink="/catalogo" class="button">Explorar catálogo <span aria-hidden="true">↗</span></a><a href="#capacidades" class="home-link">Descubrir la plataforma ↓</a></div>
        <div class="home-hero-meta"><span>01 / Diseño constructivo</span><span>02 / Datos interoperables</span><span>03 / Decisiones informadas</span></div>
      </div>
      <div class="home-hero-visual" role="img" aria-label="Axonometría conceptual original de un cerramiento multicapa y sus datos conectados">
        <svg viewBox="0 0 660 590" xmlns="http://www.w3.org/2000/svg" fill="none">
          <defs><linearGradient id="hero-surface" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#4cb8a2"/><stop offset="1" stop-color="#144f53"/></linearGradient><pattern id="hero-grid" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" stroke="#a0d9cc" stroke-opacity=".08"/></pattern></defs>
          <rect width="660" height="590" fill="url(#hero-grid)"/>
          <path d="M69 426 331 558 598 419M69 426V160M598 419V160" stroke="#8ccfbe" stroke-dasharray="4 8" stroke-opacity=".36"/>
          <g stroke="#c2f4e6" stroke-width="1.4" stroke-linejoin="round">
            <path d="M116 178 334 63 548 178 330 297Z" fill="#3d8c85"/>
            <path d="M116 178v50l214 119v-50z" fill="#285e60"/>
            <path d="M330 297v50l218-119v-50z" fill="#1f4f55"/>
            <path d="M109 257 326 370 541 257 326 143Z" fill="#8ac9b6" fill-opacity=".53"/>
            <path d="M109 257v42l217 116v-45z" fill="#63a79e"/>
            <path d="M326 370v45l215-116v-42z" fill="#397f7b"/>
            <path d="M97 342 320 458 554 339 333 223Z" fill="url(#hero-surface)"/>
            <path d="M97 342v49l223 122v-55z" fill="#164f54"/>
            <path d="M320 458v55l234-125v-49z" fill="#113e45"/>
            <path d="m130 358 188 97m-156-113 190 101m-155-116 191 101m-156-118 192 101" stroke="#c9fff1" stroke-opacity=".35"/>
          </g>
          <g stroke="#bef5dd" stroke-width="1" stroke-dasharray="4 5" opacity=".85"><path d="M334 63V23m214 155 60-34m-288 369v49M97 342l-57 28m514-31 60 24"/></g>
          <g font-family="sans-serif" font-size="13" letter-spacing="1.8" fill="#e0f9ee"><text x="342" y="24">01 GEOMETRÍA</text><text x="456" y="118">02 CAPAS</text><text x="380" y="556">03 MATERIALES</text><text x="17" y="398">IFC</text></g>
          <g fill="#9cebd6"><circle cx="334" cy="63" r="4"/><circle cx="548" cy="178" r="4"/><circle cx="320" cy="513" r="4"/><circle cx="97" cy="342" r="4"/></g>
        </svg>
        <div class="hero-data hero-data-a"><b>BIM</b><small>Geometría y propiedades</small></div>
        <div class="hero-data hero-data-b"><b>BC3 + EPD</b><small>Coste e impacto</small></div>
      </div>
    </div>
  </section>
  <section class="home-intro container" id="capacidades">
    <div class="home-section-kicker">01 / Una visión integrada</div>
    <div class="home-two"><h2>Del elemento constructivo<br><em>al conocimiento conectado.</em></h2><p>METRA conecta la clasificación de sistemas constructivos con sus modelos IFC, magnitudes técnicas, costes, impactos ambientales y documentos de procedencia. Sin convertir la información técnica en una tienda.</p></div>
    <div class="home-pillars">
      @for(p of pillars;track p.letter){<article class="home-pillar"><span class="pillar-index">{{p.number}} / {{p.letter}}</span><app-architectural-glyph [system]="p.icon" [label]="p.name"/><h3>{{p.name}}</h3><p>{{p.copy}}</p></article>}
    </div>
  </section>
  <section class="home-process" id="metodo"><div class="container">
    <div class="home-section-kicker">02 / Recorrido técnico</div>
    <div class="home-two"><h2>Explorar. Inspeccionar.<br><em>Comprender.</em></h2><p>Una secuencia coherente que relaciona la pieza representada con sus características, la documentación disponible y las alternativas constructivas.</p></div>
    <div class="home-process-diagram">
      @for(step of process;track step.number){<div class="home-process-step"><small>{{step.number}}</small><strong>{{step.title}}</strong><span>{{step.copy}}</span></div>}
    </div>
  </div></section>
  <section class="home-interoperability container">
    <div class="home-section-kicker">03 / Interoperabilidad abierta</div>
    <div class="home-two"><h2>Distintas fuentes.<br><em>Una ficha constructiva.</em></h2><p>El modelo geométrico, la estructura de costes y la información ambiental mantienen su procedencia y sus propios permisos. Vinculación no equivale a certificación.</p></div>
    <div class="home-flow" role="img" aria-label="Fuentes IFC, BC3, EPD y metadatos conectadas a la ficha de una solución">
      <div class="home-flow-sources"><span>IFC<small>Geometría</small></span><span>BC3<small>Costes</small></span><span>EPD<small>Ambiente</small></span><span>DATA<small>Prestaciones</small></span></div>
      <div class="home-flow-lines" aria-hidden="true">⌁───────⌁</div><div class="home-flow-result"><app-architectural-glyph system="MOD"/><strong>Ficha METRA</strong><small>Solución · versión · procedencia</small></div>
    </div>
  </section>
  <section class="home-featured"><div class="container">
    <div class="home-section-kicker">04 / Catálogo publicado</div>
    <div class="home-two"><h2>Soluciones para explorar.</h2><a class="home-text-link" routerLink="/catalogo">Abrir catálogo completo ↗</a></div>
    <div class="home-featured-grid">
      @for(s of featured();track s.route){<a class="home-feature-card" [routerLink]="s.route"><div class="home-feature-art"><app-architectural-glyph [system]="s.code"/></div><div class="home-feature-info"><span>{{s.kind}} · {{s.code}}</span><strong>{{s.name}}</strong><small>Explorar ficha técnica ↗</small></div></a>}
      @empty{<div class="home-feature-empty"><strong>Sin fichas públicas disponibles</strong><p>Los registros aparecerán aquí cuando hayan superado el procedimiento de publicación. Sus documentos requieren autorización independiente.</p><a routerLink="/catalogo">Consultar el catálogo →</a></div>}
    </div>
  </div></section>
  <section class="home-roles container" id="fabricantes">
    <article><span class="home-section-kicker">05 / Fabricantes</span><h2>Del producto a la ficha técnica.</h2><p>Gestión de productos, revisiones, documentos IFC y datos económicos y ambientales; publicación bajo validación administrativa.</p><a routerLink="/acceso">Acceso de fabricantes ↗</a></article>
    <article><span class="home-section-kicker">06 / Administración</span><h2>Datos con contexto y trazabilidad.</h2><p>Clasificación, revisión documental, autorización de visualización, publicación y auditoría con roles diferenciados.</p><a routerLink="/catalogo">Explorar información pública ↗</a></article>
  </section>
  <section class="home-end"><div class="container"><span>METRA · Materiales · Economía · Trazabilidad · Recursos · Ambiente</span><h2>Cada componente.<br>Todos sus datos.</h2><a class="button" routerLink="/catalogo">Explorar el catálogo ↗</a></div></section>
</div>`})
export class HomeComponent implements OnInit {
  private api=inject(ApiService);
  featured=signal<{kind:string;name:string;code:string;route:string[]}[]>([]);
  readonly pillars=[
    {letter:'M',number:'01',name:'Materiales',icon:'INT.PAR',copy:'Composición, materiales, sistemas y características constructivas.'},
    {letter:'E',number:'02',name:'Economía',icon:'EST',copy:'Costes, mediciones, partidas, presupuestos y datos BC3.'},
    {letter:'T',number:'03',name:'Trazabilidad',icon:'ENV.CUB',copy:'Fuentes documentales, versiones, permisos y revisión.'},
    {letter:'R',number:'04',name:'Recursos',icon:'MOD',copy:'Fabricantes, familias de soluciones y relaciones técnicas.'},
    {letter:'A',number:'05',name:'Ambiente',icon:'ENV.FAC',copy:'Indicadores ambientales, módulos de ciclo de vida y EPD.'}
  ];
  readonly process=[
    {number:'01',title:'Descubrir',copy:'Clasificación y filtros del catálogo.'},
    {number:'02',title:'Visualizar',copy:'Inspección axonométrica del modelo IFC.'},
    {number:'03',title:'Comprender',copy:'Capas, propiedades y prestaciones.'},
    {number:'04',title:'Analizar',copy:'Economía, ambiente y procedencia.'},
    {number:'05',title:'Comparar',copy:'Dos alternativas con límites técnicos explícitos.'},
    {number:'06',title:'Conectar',copy:'Documentos y fabricantes.'}
  ];
  async ngOnInit(){
    const results=await Promise.allSettled([
      this.api.page<Generic>('/generic-solutions',{page:1,page_size:3,sort:'code'}),
      this.api.page<Product>('/products',{page:1,page_size:3,sort:'code'})
    ]);
    const found:{kind:string;name:string;code:string;route:string[]}[]=[];
    if(results[0].status==='fulfilled')for(const s of results[0].value.data)found.push({kind:'Genérica',name:s.name_es,code:s.code,route:['/generica',s.id]});
    if(results[1].status==='fulfilled')for(const s of results[1].value.data)found.push({kind:'Comercial',name:s.published?.name_es||s.code,code:s.code,route:['/producto',s.id]});
    this.featured.set(found.slice(0,4));
  }
}
