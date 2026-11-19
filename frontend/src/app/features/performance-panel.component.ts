import {Component,Input} from '@angular/core';
import {DeclaredValuesComponent} from './declared-values.component';
import {esNumber,humanizeTechnicalKey} from '../core/technical-terminology';

@Component({selector:'app-performance-panel',standalone:true,imports:[DeclaredValuesComponent],styleUrl:'./technical-visuals.component.css',template:`
<section aria-label="Prestaciones técnicas de la solución">
  <app-declared-values [values]="technical" label="Prestaciones del registro original" empty="Sin prestaciones originales estructuradas."/>
  @if(demo){
    <div class="demo-warning"><b>MAGNITUDES DIDÁCTICAS · SIN VALIDAR</b><span>Escenario generado para mostrar la interfaz. No constituyen prestaciones de fabricante ni resultados de ensayos.</span></div>
    <div class="overview-indicators" aria-label="Indicadores de demostración">
      @for(item of metrics();track item.key){<article class="overview-metric"><small>{{humanizeTechnicalKey(item.key)}}</small><strong>{{esNumber(item.value)}}</strong><span>{{item.unit}}</span></article>}
    </div>
  }
</section>`})
export class PerformancePanelComponent {
  @Input() technical:unknown;@Input() demo:any;
  readonly humanizeTechnicalKey=humanizeTechnicalKey;
  readonly esNumber=esNumber;
  metrics():{key:string;value:number;unit:string}[]{return Object.entries(this.demo?.technical||{}).map(([key,raw])=>({key,...(raw as {value:number;unit:string})}))}
}
