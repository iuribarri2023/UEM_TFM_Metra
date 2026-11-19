import {Component,Input,OnChanges,signal} from '@angular/core';
import {esNumber} from '../core/technical-terminology';

interface DiagramElement{name:string;material:string;function:string;thickness:number|null;source:string;pattern:string;quantity:string;details:[string,string][]}
@Component({selector:'app-composition-diagram',standalone:true,styleUrl:'./technical-visuals.component.css',template:`
<section class="composition-visual" aria-label="Composición constructiva">
  <header class="visual-heading"><div><span class="eyebrow">Lectura constructiva</span><h3>{{mode==='layers'?'Sección multicapa':'Esquema de componentes'}}</h3></div><span class="diagram-status">{{source==='real'?'Composición de origen':'Composición de referencia'}}</span></header>

  @if(elements.length){
    <div class="diagram-scale">{{proportional?'Espesores declarados en milímetros · proporciones relativas':'Esquema no proporcional · espesores incompletos o no aplicables'}}</div>
    <div class="layer-diagram" [class.component-diagram]="mode==='components'" role="group" aria-label="Seleccionar una capa o componente para inspeccionarlo">
      @for(layer of elements;track $index){<button type="button" class="layer-shape" [class.layer-active]="selected()===$index"
          [class.pattern-dense]="layer.pattern==='dense'" [class.pattern-diagonal]="layer.pattern==='diagonal'"
          [class.pattern-dots]="layer.pattern==='dots'" [class.pattern-linear]="layer.pattern==='linear'"
          [style.flex]="proportional?(layer.thickness||1):1" (click)="selected.set($index)"
          [attr.aria-label]="'Capa '+($index+1)+': '+layer.name" [attr.aria-pressed]="selected()===$index">
          <svg viewBox="0 0 100 64" aria-hidden="true" class="layer-art"><path d="M6 24 66 5 94 19 34 39Z M6 24v20l28 15V39m0 20 60-20V19" fill="none" stroke="currentColor" stroke-width="2"/></svg><span class="layer-marker">{{($index+1).toString().padStart(2,'0')}}</span></button>}
    </div>
    <div class="layer-legend">@for(layer of elements;track $index){<button type="button" [class.selected]="selected()===$index" (click)="selected.set($index)"><span>{{($index+1).toString().padStart(2,'0')}}</span>{{layer.name}}</button>}</div>
    @if(elements[selected()];as active){<div class="layer-inspection"><div class="visual-heading"><h3>{{active.name}}</h3><span>{{source==='real'?'Dato de origen':'Estimación'}}</span></div>
      <dl><div><dt>Material</dt><dd>{{active.material||'No especificado'}}</dd></div><div><dt>Función</dt><dd>{{active.function||'No especificada'}}</dd></div><div><dt>Espesor</dt><dd>{{active.thickness!==null?esNumber(active.thickness)+' mm':'No disponible'}}</dd></div><div><dt>Cantidad</dt><dd>{{active.quantity||'No cuantificada'}}</dd></div></dl>
      @if(active.details.length){<dl>@for(property of active.details;track property[0]){<div><dt>{{property[0]}}</dt><dd>{{property[1]}}</dd></div>}</dl>}</div>}
  }@else{<p class="muted">No consta una descomposición constructiva representable.</p>}
</section>`})
export class CompositionDiagramComponent implements OnChanges {
  @Input() composition:any[]=[];
  @Input() demo:any;
  selected=signal(0);elements:DiagramElement[]=[];mode='layers';source='real';proportional=false;
  readonly esNumber=esNumber;
  ngOnChanges(){
    const original=Array.isArray(this.composition)?this.composition.filter(x=>x&&typeof x==='object'):[];
    const demo=this.demo?.composition;
    const rows=original.length?original:demo?.elements||[];
    this.source=original.length&&!original.every(x=>x.source_type==='ESTIMATED')?'real':'demo';
    this.elements=rows.map((x:any,i:number)=>{
      const field=x.thickness_mm??x.thickness?.value??x.properties?.thickness_mm;
      const thickness=typeof field==='number'&&field>0&&Number.isFinite(field)?field:null;
      const named=(v:any)=>typeof v==='string'?v:(typeof v==='number'?String(v):'');
      return {name:named(x.name_es||x.name||x.material)||'Elemento '+(i+1),
        material:named(x.material?.name_es||x.material||x.properties?.material_family||x.family),
        function:named(x.function||x.role),thickness,source:this.source,
        quantity:named(x.quantity?.value??x.quantity)+(x.quantity?.unit?' '+x.quantity.unit:''),
        details:Object.entries(x.properties||{}).flatMap(([key,value])=>
          typeof value==='number'||typeof value==='string'?[[key.replaceAll('_',' '),String(value)] as [string,string]]:[]),
        pattern:['dense','diagonal','dots','linear'][i%4]};
    });
    this.mode=original.length?(this.elements.every(x=>x.thickness!==null)?'layers':'components'):demo?.mode||'components';
    this.proportional=this.mode==='layers'&&this.elements.length>0&&this.elements.every(x=>x.thickness!==null);
    this.selected.set(0);
  }
}
