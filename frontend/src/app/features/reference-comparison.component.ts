import {Component,Input} from '@angular/core';
import {esNumber} from '../core/technical-terminology';
import {ReferenceModel,comparableReference,referenceParts} from '../core/reference-model';

@Component({selector:'app-reference-comparison',standalone:true,template:`
@if(a&&b){
  <section class="reference-comparison">
    <div class="compare-alternatives">
      @for(model of [a,b];track $index){
        <article class="compare-alternative">
          <span class="eyebrow">Solución {{$index===0?'A':'B'}} · estimación</span>
          <h3>{{esNumber(model.total)}} {{model.currency||model.unit}} / {{model.functional_unit}}</h3>
          @for(part of parts(model);track part.label){
            <div class="scenario-bar-row">
              <div class="scenario-label"><span>{{part.label}}</span><b>{{esNumber(part.value)}} {{part.unit}}</b></div>
              <div class="scenario-bar-track"><div class="scenario-bar-fill" [style.width.%]="bar(part.value,part.label,model.total)"></div></div>
            </div>
          }
          @for(indicator of model.additional||[];track indicator.label){
            <p>{{indicator.label}} · {{esNumber(indicator.value)}} {{indicator.unit}} · {{indicator.module}}</p>
          }
        </article>
      }
    </div>
    @if(compatible(a,b)){
      <p class="compare-delta"><b>Diferencia B − A</b> {{esNumber(b.total-a.total)}} {{a.currency||a.unit}}
        @if(a.total!==0){ · {{esNumber(100*(b.total-a.total)/a.total)}} % respecto a A}
        @if(driver();as main){<br><small>Mayor contribución a la diferencia · {{main.label}} ({{esNumber(main.delta)}})</small>}
      </p>
    }@else{
      <p class="compare-warning">Las bases de cálculo difieren. Los valores se presentan por separado.</p>
    }
  </section>
}`})
export class ReferenceComparisonComponent {
  @Input() a:ReferenceModel|null=null;
  @Input() b:ReferenceModel|null=null;
  readonly esNumber=esNumber;
  readonly parts=referenceParts;
  readonly compatible=comparableReference;
  bar(value:number,label:string,total:number){
    const others=this.a&&this.b&&this.compatible(this.a,this.b)?[...this.parts(this.a),...this.parts(this.b)]:[];
    const max=others.length?Math.max(value,...others.filter(x=>x.label===label).map(x=>x.value)):total;
    return max>0?100*value/max:0;
  }
  driver(){
    if(!this.a||!this.b)return null;
    const right=this.parts(this.b);
    return this.parts(this.a).map(x=>({label:x.label,delta:(right.find(y=>y.label===x.label)?.value??0)-x.value}))
      .sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta))[0]??null;
  }
}
