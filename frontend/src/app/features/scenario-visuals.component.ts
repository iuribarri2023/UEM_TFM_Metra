import {Component,Input} from '@angular/core';
import {esNumber} from '../core/technical-terminology';
import {ReferenceModel,referenceParts} from '../core/reference-model';

@Component({selector:'app-scenario-visuals',standalone:true,styleUrl:'./technical-visuals.component.css',template:`
@if(scenario;as model){
  <section class="scenario-visuals" [attr.aria-label]="kind==='economic'?'Desglose del coste':'Indicadores ambientales'">
    <div class="visual-heading"><span class="eyebrow">Modelo de referencia</span><span class="diagram-status">Estimado</span></div>
    <div class="scenario-total">
      <small>{{kind==='economic'?'Coste por unidad funcional':'GWP · producción y transporte'}}</small>
      <strong>{{esNumber(model.total)}} <span>{{model.currency||model.unit}} / {{model.functional_unit}}</span></strong>
      @if(model.period){<p>{{model.location}} · {{model.period}}</p>}
    </div>
    <div class="scenario-bars">
      @for(part of parts(model);track part.label){
        <div class="scenario-bar-row"><div class="scenario-label">
          <span>{{part.label}} @if(part.quantity!==undefined){<small>· {{esNumber(part.quantity)}} {{part.quantityUnit}}</small>}</span>
          <strong>{{esNumber(part.value)}} {{part.unit}}</strong></div>
          <div class="scenario-bar-track"><div class="scenario-bar-fill" [style.width.%]="share(part.value,model.total)"></div></div>
        </div>
      }
    </div>
    @for(indicator of model.additional||[];track indicator.label){
      <p><strong>{{indicator.label}}</strong> · {{esNumber(indicator.value)}} {{indicator.unit}} / {{model.functional_unit}} · {{indicator.module}}</p>
    }
    <details class="scenario-caveat"><summary>Base del cálculo</summary>
      <p>{{model.method}} · {{model.scope}} · {{model.quantity}} {{model.functional_unit}}.</p>
      <p>{{kind==='economic'?'Importe orientativo sujeto a medición y condiciones de obra.':'Indicador modelado con factores de referencia.'}}</p>
    </details>
  </section>
}`})
export class ScenarioVisualsComponent {
  @Input() scenario:ReferenceModel|null=null;
  @Input() kind:'economic'|'environmental'='economic';
  readonly esNumber=esNumber;
  readonly parts=referenceParts;
  share(value:number,total:number){return total>0?100*value/total:0;}
}
