import {Component,computed,input} from '@angular/core';
import {CanonicalSolution,TemplateField} from '../core/canonical';
import {esNumber} from '../core/technical-terminology';

@Component({selector:'app-canonical-properties',standalone:true,template:`
  <h2>Prestaciones</h2>
  <p class="muted">{{solution().template.code}} · Plantilla {{solution().template.version}}</p>
  @for(group of groups();track group.label){
    <section class="performance-group">
      <h3>{{group.label}}</h3>
      <div class="performance-cards">
        @for(field of group.fields;track field.code){
          @let cell=solution().properties[field.code];
          @if(cell){<article>
            <small>{{field.name_es||field.label||field.code}}</small>
            <strong>{{display(cell.value)}} @if(cell.value!==null&&cell.unit!=='unit'){<span>{{cell.unit}}</span>}</strong>
            <span class="performance-origin">{{cell.source_type==='DEMO_SIMULATED'?'Valor estimado':cell.source_type==='CALCULATED'?'Calculado':cell.source_type==='SOURCE_DECLARED'?'Declarado':'Pendiente de documentación'}}</span>
          </article>}
        }
      </div>
    </section>
  }@empty{<p>Plantilla sin campos definidos.</p>}
`})
export class CanonicalPropertiesComponent {
  solution=input.required<CanonicalSolution>();
  groups=computed(()=>{
    const groups=new Map<string,TemplateField[]>();
    for(const field of this.solution().template.fields){
      const label=field.display_group||'Características técnicas';
      groups.set(label,[...(groups.get(label)||[]),field]);
    }
    return Array.from(groups,([label,fields])=>({label,fields}));
  });
  display(value:unknown){
    if(typeof value==='number')return esNumber(value);
    if(typeof value==='boolean')return value?'Sí':'No';
    return value??'Sin dato';
  }
}
