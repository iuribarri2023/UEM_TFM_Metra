import {Component,Input} from '@angular/core';
import {referenceOf} from '../core/reference-model';
import {CanonicalSolution} from '../core/canonical';
import {ArchitecturalGlyphComponent} from '../core/architectural-glyph.component';
import {esNumber} from '../core/technical-terminology';

@Component({selector:'app-solution-overview',standalone:true,imports:[ArchitecturalGlyphComponent],styleUrl:'./technical-visuals.component.css',template:`
<section class="solution-visual-overview" aria-label="Resumen constructivo">
  <div class="overview-art"><app-architectural-glyph [system]="subsystem||code"/><div><span class="overview-kicker">{{type}} / FICHA TÉCNICA</span><strong>{{name}}</strong><small>{{code}}</small></div></div>
  <div class="overview-identifiers"><span><small>Unidad funcional</small><b>{{unit||'No declarada'}}</b></span><span><small>Fabricante</small><b>{{manufacturer||'Referencia independiente'}}</b></span><span><small>Estado documental</small><b>{{documents}} documentos visibles</b></span></div>
  @if(description){<p class="overview-intro">{{description}}</p>}
  @if(subsystem){<p class="overview-origin">Clasificación · {{subsystem}}</p>}
  <div class="overview-indicators">
    @for(metric of metrics();track metric.label){<div class="overview-metric"><small>{{metric.label}}</small><strong>{{metric.value}}</strong><span>{{metric.unit}}</span></div>}
  </div>

</section>`})
export class SolutionOverviewComponent {
  @Input() canonical?:CanonicalSolution;
  @Input() economic:unknown;
  @Input() environmental:unknown;
  @Input() subsystem='';
  @Input() code='';@Input() name='';@Input() type='';@Input() unit='';
  @Input() manufacturer='';@Input() description='';@Input() documents=0;
  metrics(){
    const keys=['primary_material','total_thickness_mm','depth_mm','surface_mass','thermal_transmittance'];
    const rows=keys.flatMap(code=>{
      const field=this.canonical?.template.fields.find(x=>x.code===code);
      const value=this.canonical?.properties[code];
      if(!field||!value||value.value===null)return [];
      return [{label:field.label,value:typeof value.value==='number'?esNumber(value.value):String(value.value),
        unit:value.unit==='unit'?'':value.unit}];
    }).slice(0,4);
    for(const [label,source] of [['Coste estimado',this.economic],['GWP estimado',this.environmental]] as const){
      const model=referenceOf(source);
      if(model) rows.push({label,value:esNumber(model.total),unit:(model.currency||model.unit)+' / '+model.functional_unit});
    }
    return rows;
  }
}
