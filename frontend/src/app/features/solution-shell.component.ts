import {Component,Input,OnChanges,output,signal,viewChild} from '@angular/core';
import {NgTemplateOutlet} from '@angular/common';
import {UiIcon,UiIconComponent} from '../core/ui-icon.component';
import {Asset} from '../core/api';
import {ViewerHostComponent} from './viewer-host.component';

export const SOLUTION_SECTIONS=['Visión general','Prestaciones','Composición','Economía','Ambiente','Documentos','Historial'] as const;
export type SolutionSection=typeof SOLUTION_SECTIONS[number];

const BIM_MESSAGES:Record<string,string>={
  NO_IFC:'Esta ficha no tiene IFC asociado.',
  PRIVATE:'El IFC está registrado, pero su visualización pública no está autorizada.',
  PROCESSING:'El IFC sigue en procesamiento.',
  INVALID:'El IFC no superó el procesamiento.',
  MISSING:'El archivo IFC original no está disponible.',
  CORRUPT:'El archivo IFC no coincide con su huella SHA-256.',
  VIEWABLE:'No se ha podido cargar el IFC autorizado.'
};

@Component({selector:'app-solution-shell',standalone:true,imports:[ViewerHostComponent,NgTemplateOutlet,UiIconComponent],template:`
<div class="mobile-inspection-toggle" role="group" aria-label="Vista de la ficha">
    <button type="button" [attr.aria-pressed]="mobilePanel()==='bim'" (click)="mobilePanel.set('bim')">Modelo BIM</button>
    <button type="button" [attr.aria-pressed]="mobilePanel()==='data'" (click)="mobilePanel.set('data')">Información técnica</button>
  </div>
<div class="metra-detail solution-grid" [class.show-mobile-bim]="mobilePanel()==='bim'" [class.show-mobile-data]="mobilePanel()==='data'">
  <section class="panel bim-main" aria-label="Modelo constructivo">
    <div class="model-panel-head">
      <div><span class="eyebrow">Modelo constructivo</span><h2>Visor BIM</h2></div>
      @if(models().length>1){
        <label>Modelo activo<select [value]="active()" (change)="changeModel($event)">
          @for(model of models();track model.id){<option [value]="model.id">{{model.original_name}}</option>}
        </select></label>
      }
    </div>
    @if(active()){
      <app-viewer-host [assetId]="active()" [revisionId]="revisionId" [externalInspector]="true" (selectionChanged)="context($event)"/>
    }@else{
      <div class="model-empty"><span>IFC</span><h2>{{review?'Vista previa no disponible':'Modelo público no disponible'}}</h2><p>{{bimReason()}}</p></div>
    }
  </section>
  <section class="panel detail-inspector" aria-label="Información de la ficha">
    <div class="inspector-head"><span class="eyebrow">Ficha técnica</span><h2>Inspector</h2></div>
    <div class="solution-inspection">
      <nav class="solution-nav" aria-label="Secciones de la ficha">
        @for(item of sections;track item){
          <button type="button" [attr.aria-current]="!elementContext()&&item===section?'true':null" (click)="showSection(item)">
            <app-ui-icon [name]="icons[item]"/>{{item}}
          </button>
          @if(item==='Composición'){
            <button type="button" [disabled]="!active()" [attr.aria-current]="elementContext()?'true':null" (click)="elementContext.set(true)">
              <app-ui-icon name="cube"/>BIM
            </button>
          }
        }
      </nav>
      <div class="solution-inspector-content">
        @if(elementContext()){
          <h3>Componente IFC</h3>
          @if(viewer()?.ready()){
            <ng-container [ngTemplateOutlet]="viewer()?.inspectionTemplate() ?? null"/>
          }@else{<p class="muted">El modelo todavía no está listo.</p>}
        }@else{<ng-content/>}
      </div>
    </div>
  </section>
</div>`})
export class SolutionShellComponent implements OnChanges {
  @Input({required:true}) assets:Asset[]=[];
  @Input() bimStatus?:string;
  @Input() review=false;
  @Input() revisionId='';
  @Input() section:SolutionSection='Visión general';
  sectionChange=output<SolutionSection>();
  readonly sections=SOLUTION_SECTIONS;
  readonly icons:Record<SolutionSection,UiIcon>={
    'Visión general':'overview','Prestaciones':'properties','Composición':'layers',
    'Economía':'costs','Ambiente':'environment','Documentos':'document','Historial':'history'
  };
  viewer=viewChild(ViewerHostComponent);
  elementContext=signal(false);
  mobilePanel=signal<'bim'|'data'>('bim');
  context(selected:boolean){this.elementContext.set(selected)}
  showSection(section:SolutionSection){this.elementContext.set(false);this.mobilePanel.set('data');this.sectionChange.emit(section)}
  models=signal<Asset[]>([]);
  active=signal('');
  ngOnChanges(){
    const allowed=this.assets.filter(asset=>asset.file_type==='IFC'&&(this.review||asset.public_view_allowed)&&asset.processing_status==='VALID');
    this.models.set(allowed);
    if(!allowed.some(asset=>asset.id===this.active()))this.active.set(allowed[0]?.id||'');
  }
  changeModel(event:Event){this.elementContext.set(false);this.active.set((event.target as HTMLSelectElement).value)}
  bimReason(){return BIM_MESSAGES[this.bimStatus||'']||'Estado BIM no disponible.'}
}
