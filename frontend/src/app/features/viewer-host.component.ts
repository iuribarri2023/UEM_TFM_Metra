import {Component,ElementRef,Input,OnDestroy,ViewChild,inject,signal,computed,AfterViewInit,OnChanges,output,viewChild,TemplateRef} from '@angular/core';
import {UiIconComponent} from '../core/ui-icon.component';
import {NgTemplateOutlet} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {ApiService,Asset,problem} from '../core/api';
import {IfcViewer} from '../../bim/viewer';

interface ComponentLink {id:string;kind:string;document_id:string;document_name:string;concept_code?:string;material?:string;unit?:string}

interface TreeNode {id:number;name:string|null;ifc_class:string;global_id:string;composition_parent_id:number|null;composition_relation:string|null}
interface IfcElement extends TreeNode {psets?:Record<string,unknown>;qto?:Record<string,unknown>;materials?:string[];classifications?:string[]}

@Component({selector:'app-viewer-host',standalone:true,imports:[FormsModule,NgTemplateOutlet,UiIconComponent],styleUrl:'./viewer-host.component.css',template:`
<section #workspace class="bim-shell" aria-label="Visor IFC 3D">
  <div class="bim-toolbar" aria-label="Herramientas BIM">
    <div class="bim-toolgroup" role="group" aria-label="Cámara">
      <button type="button" [disabled]="!ready()" (click)="perform('fit')" aria-label="Encuadrar" title="Encuadrar selección o modelo"><app-ui-icon name="fit"/></button>
      <button type="button" [disabled]="!ready()" (click)="perform('reset')" aria-label="Reiniciar" title="Reiniciar escena"><app-ui-icon name="history"/></button>
      <label class="bim-view-label">Vista<select [disabled]="!ready()" (change)="changeView($event)">
        <option value="iso">Axonométrica</option><option value="front">Frontal</option><option value="top">Superior</option><option value="side">Lateral</option>
      </select></label>
      @if(fullscreenSupported){
        <button type="button" [disabled]="!ready()" (click)="fullscreen(workspace)" aria-label="Pantalla completa" title="Entrar o salir de pantalla completa"><app-ui-icon name="fullscreen"/></button>
      }
    </div>
    <div class="bim-toolgroup" role="group" aria-label="Selección y visibilidad">
      <button type="button" [disabled]="!ready()||!selection().length" (click)="clearSelection()" aria-label="Limpiar selección" title="Limpiar selección"><app-ui-icon name="clear"/></button>
      <button type="button" [disabled]="!ready()||visibilityBusy()" (click)="perform('show')" aria-label="Mostrar todo" title="Mostrar todo"><app-ui-icon name="eye"/></button>
      <button type="button" [disabled]="!ready()||visibilityBusy()||!selection().length" (click)="perform('isolate')" aria-label="Aislar" title="Aislar selección"><app-ui-icon name="isolate"/></button>
      <button type="button" [disabled]="!ready()||visibilityBusy()||!selection().length" (click)="perform('hide')" aria-label="Ocultar selección" title="Ocultar selección"><app-ui-icon name="hidden"/></button>
    </div>
    <div class="bim-toolgroup" role="group" aria-label="Análisis">
      <button type="button" [disabled]="!ready()" [attr.aria-pressed]="cut()" (click)="toggleCut()" aria-label="Corte horizontal" title="Activar o retirar corte horizontal"><app-ui-icon name="section"/></button>
      @if(cut()){
        <label>Altura del corte <input type="range" min="1" max="99" [value]="cutHeight" (change)="adjustCut($event)"></label>
      }
    </div>
  </div>
  <div class="bim-stage">
    <div #host class="viewer-canvas" role="region" aria-label="Modelo BIM. Clic para seleccionar, arrastre para orbitar, doble clic para encuadrar."
         (pointerdown)="pointerDown($event)" (pointerup)="pointerUp($event)"
         (pointermove)="pointerMove($event)" (pointercancel)="press=undefined" (dblclick)="fitHit($event)"></div>
    @if(ready()){
      <details class="bim-overlay" (toggle)="openTree($event)">
        <summary>Árbol de componentes <span>{{nodes().length}}</span></summary>
        <div class="bim-tree-panel">
          <label>Buscar componentes<input type="search" [ngModel]="query()" (ngModelChange)="setQuery($event)" placeholder="Nombre, clase o GlobalId"></label>
          <label>Organización<select [ngModel]="treeMode()" (ngModelChange)="setMode($event)">
            <option value="class">Clase IFC</option><option value="composition">Composición IFC</option>
          </select></label>
          @if(indexTruncated()){<p class="small muted">Índice parcial. El árbol muestra hasta 10.000 productos.</p>}
          @if(treeLoading()){<p role="status">Cargando componentes…</p>}
          @if(treeMode()==='class'){
            @for(group of groups();track group.name){
              <div class="bim-class">
                <div class="bim-tree-row">
                  <button class="bim-icon" type="button" [attr.aria-expanded]="expanded().has(group.name)" [attr.aria-label]="'Expandir '+group.name" (click)="toggleGroup(group.name)"><app-ui-icon [name]="expanded().has(group.name)?'down':'arrow'"/></button>
                  <button class="bim-name" type="button" [attr.aria-pressed]="allSelected(group.all)" (click)="selectGroup(group.all)">{{group.name}} <small>{{group.matches.length===group.all.length?group.all.length:group.matches.length+'/'+group.all.length}}</small></button>
                  <button class="bim-icon" type="button" [disabled]="visibilityBusy()" [attr.aria-label]="eyeLabel(group.name,group.all)" (click)="toggleVisibility(group.all)"><app-ui-icon [name]="allHidden(group.all)?'hidden':'eye'"/></button>
                </div>
                @if(expanded().has(group.name)||query()){
                  @for(item of group.matches.slice(0,limit());track item.id){
                    <ng-container [ngTemplateOutlet]="itemRow" [ngTemplateOutletContext]="{$implicit:item,depth:1}"/>
                  }
                  @if(group.matches.length>limit()){<button class="text-link" type="button" (click)="more()">Más componentes</button>}
                }
              </div>
            }@empty{<p class="small muted">Sin coincidencias en el índice IFC.</p>}
          }@else{
            @for(row of hierarchy().slice(0,limit());track row.node.id){
              <ng-container [ngTemplateOutlet]="itemRow" [ngTemplateOutletContext]="{$implicit:row.node,depth:row.depth}"/>
            }@empty{<p class="small muted">Sin coincidencias en el índice IFC.</p>}
            @if(hierarchy().length>limit()){<button class="text-link" type="button" (click)="more()">Más componentes</button>}
            @if(!hasComposition()){<p class="small muted">Sin relaciones de composición indexadas. Si el IFC es anterior, vuelve a procesarlo desde Documentos.</p>}
          }
        </div>
      </details>
    }
  </div>
  <ng-template #itemRow let-item let-depth="depth">
    <div class="bim-tree-row bim-item" [style.--depth]="depth">
      <button class="bim-name" type="button" [attr.aria-pressed]="selectedIds().has(item.global_id)"
        (click)="choose(item.global_id,$event.ctrlKey||$event.metaKey||$event.shiftKey)">
        {{item.name||item.ifc_class}} <small>#{{item.id}} {{item.composition_relation||''}}</small>
      </button>
      <button class="bim-icon" type="button" [disabled]="visibilityBusy()" [attr.aria-label]="eyeLabel(item.name||item.ifc_class,[item])" (click)="toggleVisibility([item])"><app-ui-icon [name]="allHidden([item])?'hidden':'eye'"/></button>
    </div>
  </ng-template>
  <footer class="bim-status" aria-live="polite">{{loading()?phase():ready()?'Modelo cargado · '+selection().length+' en selección':'Visor sin modelo'}}</footer>
  @if(error()){<p class="error" role="alert">{{error()}}</p>}
  @if(ready()&&!externalInspector){
    <details class="bim-inspector" [open]="inspectorOpen()" (toggle)="syncInspector($event)">
      <summary>Inspector del componente</summary>
      <ng-container [ngTemplateOutlet]="inspectionTemplate() ?? null"/>
    </details>
  }
  <p class="bim-source-note">La visualización transfiere el IFC original autorizado. Sus bytes se pueden recuperar en el navegador aunque la descarga directa esté deshabilitada.</p>
</section>
<ng-template #inspection>
      @if(selection().length>1){<p>{{selection().length}} elementos seleccionados. Se muestran los datos del elemento activo.</p>}
      @if(!selected()){<p class="muted">Selecciona un objeto en el lienzo o en el árbol.</p>}
      @else if(!selectedElement()){<p role="status">{{propertiesLoading()?'Cargando propiedades…':'Sin propiedades indexadas para '+selected()}}</p>}
    @if(selectedElement();as element){
      <p class="small">Selección · {{element.name || element.ifc_class}} · {{element.global_id}}</p>
      <p class="small">{{element.ifc_class}} · Entidad #{{element.id}}</p>
      @if(element.composition_relation){
        <p>Composición · {{element.composition_relation}} · Padre #{{element.composition_parent_id}}</p>
      }
      @if(element.classifications?.length){<p>Clasificación · {{element.classifications?.join(', ')}}</p>}
      @if(element.materials?.length){<p>Materiales · {{element.materials?.join(', ')}}</p>}
      @for(group of propertyGroups(element);track group.name){
        <details class="component"><summary>{{group.name}}</summary>
          @for(entry of group.rows;track entry[0]){<dl class="property-row"><dt>{{entry[0]}}</dt><dd>{{formatProperty(entry[1])}}</dd></dl>}
        </details>
      }
      @if(revisionId){
        <h3>Vínculos económicos y ambientales</h3>
        @if(linkError()){<p class="error" role="alert">{{linkError()}}</p>}
        @if(linksLoading()){<p role="status">Consultando vínculos…</p>}
        @for(link of links();track link.id){
          <div class="file-row"><span>{{link.kind}} · {{link.document_name}}
            {{link.concept_code||''}} {{link.material||''}} {{link.unit||''}}</span>
            <button class="text-link" (click)="downloadLinked(link)">Descargar</button>
            @if(editable){<button class="text-link" (click)="removeLink(link)">Retirar vínculo</button>}
          </div>
        }@empty{
          @if(!linksLoading()&&!linkError()){<p class="muted">Sin vínculos BC3 o EPD disponibles para este componente.</p>}
        }
        @if(editable&&targets.length){
          <form class="form-grid" (ngSubmit)="createLink(element)">
            <label>Documento<select name="target" [(ngModel)]="targetId" (ngModelChange)="code=''" required>
              <option value="">Seleccionar</option>
              @for(target of targets;track target.id){<option [value]="target.id">{{target.file_type}} · {{target.original_name}}</option>}
            </select></label>
            @if(targetKind()==='BC3'){<label>Código BC3<input name="code" [(ngModel)]="code" required></label>}
            @if(element.materials?.length){
              <label>Material<select name="material" [(ngModel)]="material"><option value="">Sin especificar</option>
                @for(item of element.materials;track $index){<option [value]="item">{{item}}</option>}
              </select></label>
            }
            <label>Unidad declarada<input name="unit" maxlength="100" [(ngModel)]="unit"></label>
            <label>Evidencia<input name="evidence" minlength="10" maxlength="2000" [(ngModel)]="evidence" required></label>
            <button class="button" [disabled]="!targetId||evidence.trim().length<10||linkSaving()">Vincular documento</button>
          </form>
        }
      }
    }
</ng-template>`})
export class ViewerHostComponent implements AfterViewInit,OnChanges,OnDestroy {
  @Input() assetId='';
  @Input() revisionId='';
  @Input() editable=false;
  @Input() externalInspector=false;
  selectionChanged=output<boolean>();
  inspectionTemplate=viewChild<TemplateRef<unknown>>('inspection');
  readonly fullscreenSupported=!!document.fullscreenEnabled;
  @Input() targets:Asset[]=[];
  links=signal<ComponentLink[]>([]);
  linksLoading=signal(false);linkError=signal('');linkSaving=signal(false);
  targetId='';code='';material='';unit='';evidence='';
  private selectionRun=0;
  private modelRun=0;
  private pickRun=0;
  private mounted=false;
  private destroyed=false;
  private indexRequested=false;
  private viewer?:IfcViewer;
  private download?:AbortController;
  private api=inject(ApiService);
  @ViewChild('host') host!:ElementRef<HTMLElement>;

  loading=signal(false);ready=signal(false);error=signal('');
  phase=signal('Descargando IFC');
  selection=signal<string[]>([]);
  selectedIds=computed(()=>new Set(this.selection()));
  selected=computed(()=>this.selection().at(-1)||'');
  selectedElement=signal<IfcElement|null>(null);
  propertiesLoading=signal(false);
  inspectorOpen=signal(false);
  cut=signal(false);
  cutHeight=50;
  press?:{id:number;x:number;y:number};

  nodes=signal<TreeNode[]>([]);
  query=signal('');
  treeMode=signal<'class'|'composition'>('class');
  expanded=signal<Set<string>>(new Set());
  limit=signal(30);
  treeLoading=signal(false);
  indexTruncated=signal(false);
  hidden=signal<Set<string>>(new Set());
  isolated=signal<Set<string>|null>(null);
  visibilityBusy=signal(false);
  hasComposition=computed(()=>this.nodes().some(node=>node.composition_relation));
  groups=computed(()=>{
    const grouped=new Map<string,TreeNode[]>();
    for(const node of this.nodes()){
      const rows=grouped.get(node.ifc_class)||[];
      rows.push(node);grouped.set(node.ifc_class,rows);
    }
    return [...grouped].sort(([left],[right])=>left.localeCompare(right))
      .map(([name,all])=>({name,all,matches:all.filter(node=>this.matches(node))}))
      .filter(group=>group.matches.length);
  });
  hierarchy=computed(()=>{
    const nodes=this.nodes(),ids=new Set(nodes.map(node=>node.id));
    const children=new Map<number|null,TreeNode[]>();
    for(const node of nodes){
      const parent=node.composition_parent_id;
      const key=parent!==null&&ids.has(parent)?parent:null;
      const rows=children.get(key)||[];
      rows.push(node);children.set(key,rows);
    }
    const seen=new Set<number>();
    const result:{node:TreeNode;depth:number}[]=[];
    const visit=(node:TreeNode,depth:number)=>{
      if(seen.has(node.id))return;
      seen.add(node.id);
      if(this.matches(node))result.push({node,depth});
      if(depth<40)for(const child of children.get(node.id)||[])visit(child,depth+1);
    };
    for(const node of children.get(null)||[])visit(node,0);
    for(const node of nodes)visit(node,0);
    return result;
  });

  ngAfterViewInit(){this.mounted=true;void this.mountModel()}
  ngOnChanges(){if(this.mounted&&this.assetId!==this.activeAsset)void this.mountModel()}
  private activeAsset='';
  private async mountModel(){
    const run=++this.modelRun;
    ++this.selectionRun;++this.pickRun;
    this.download?.abort();
    this.viewer?.dispose();
    this.viewer=undefined;
    this.activeAsset=this.assetId;
    this.ready.set(false);this.error.set('');this.phase.set('Descargando IFC');
    this.nodes.set([]);this.selection.set([]);this.selectedElement.set(null);this.hidden.set(new Set());this.isolated.set(null);this.visibilityBusy.set(false);
    this.links.set([]);this.linksLoading.set(false);this.linkError.set('');this.propertiesLoading.set(false);
    this.material='';this.evidence='';this.targetId='';this.code='';this.unit='';
    this.query.set('');this.limit.set(30);this.expanded.set(new Set());
    this.treeLoading.set(false);this.indexTruncated.set(false);this.indexRequested=false;
    this.cut.set(false);this.cutHeight=50;this.press=undefined;this.inspectorOpen.set(false);
    this.loading.set(!!this.assetId);
    if(!this.assetId)return;
    try{
      const download=new AbortController();
      this.download=download;
      const bytes=new Uint8Array(await this.api.bytes('/assets/'+this.assetId+'/view',download.signal));
      if(!this.current(run))return;
      const viewer=new IfcViewer();
      this.viewer=viewer;
      await viewer.mount(this.host.nativeElement,bytes,step=>{if(this.current(run))this.phase.set(step)});
      if(this.current(run))this.ready.set(true);
    }catch(e){
      if(this.current(run)){this.viewer?.dispose();this.viewer=undefined;this.error.set('No se ha podido mostrar el IFC: '+problem(e))}
    }finally{if(this.current(run)){this.download=undefined;this.loading.set(false)}}
  }
  syncInspector(event:Event){this.inspectorOpen.set((event.currentTarget as HTMLDetailsElement).open)}
  private current(run:number){return !this.destroyed&&run===this.modelRun}
  private matches(node:TreeNode){
    const query=this.query().trim().toLocaleLowerCase('es');
    return !query||[node.name,node.ifc_class,node.global_id,String(node.id)].some(value=>value?.toLocaleLowerCase('es').includes(query));
  }
  setQuery(query:string){this.query.set(query);this.limit.set(30)}
  setMode(mode:'class'|'composition'){this.treeMode.set(mode);this.limit.set(30)}
  more(){this.limit.update(limit=>limit+30)}
  toggleGroup(name:string){
    this.expanded.update(previous=>{
      const next=new Set(previous);
      if(next.has(name))next.delete(name);else next.add(name);
      return next;
    });
  }
  propertyGroups(element:IfcElement){
    return [
      ...Object.entries(element.psets||{}).map(([name,value])=>({name,value,kind:'Propiedades'})),
      ...Object.entries(element.qto||{}).map(([name,value])=>({name,value,kind:'Cantidades'}))
    ].map(({name,value,kind})=>({
      name:kind+' · '+name,
      rows:value&&typeof value==='object'?Object.entries(value).filter(([key])=>key!=='id'):[]
    }));
  }
  formatProperty(value:unknown):string {
    if(value===null||value===undefined)return '—';
    if(typeof value==='boolean')return value?'Sí':'No';
    if(typeof value==='object')return JSON.stringify(value);
    return String(value);
  }
  openTree(event:Event){
    if((event.currentTarget as HTMLDetailsElement).open&&!this.indexRequested)void this.loadTree();
  }
  private async loadTree(){
    const run=this.modelRun;
    this.indexRequested=true;this.treeLoading.set(true);
    try{
      const result=await this.api.page<TreeNode>('/documents/'+this.assetId+'/ifc-tree');
      if(this.current(run)){
        this.nodes.set(result.data.filter(item=>!!item.global_id));
        this.indexTruncated.set(!!result.meta?.truncated);
      }
    }catch(e){if(this.current(run)){this.indexRequested=false;this.error.set(problem(e))}}
    finally{if(this.current(run))this.treeLoading.set(false)}
  }
  pointerDown(event:PointerEvent){
    if(!event.isPrimary){this.press=undefined;return}
    if(event.button!==0||!this.ready())return;
    this.press={id:event.pointerId,x:event.clientX,y:event.clientY};
  }
  pointerMove(event:PointerEvent){
    if(this.press?.id===event.pointerId&&Math.hypot(event.clientX-this.press.x,event.clientY-this.press.y)>5)this.press=undefined;
  }
  pointerUp(event:PointerEvent){
    const press=this.press;
    this.press=undefined;
    if(!press||press.id!==event.pointerId||Math.hypot(event.clientX-press.x,event.clientY-press.y)>5)return;
    void this.pick(event);
  }
  private async pick(event:MouseEvent){
    const run=++this.pickRun,model=this.modelRun;
    try{
      const guid=await this.viewer?.pick(event.clientX,event.clientY);
      if(this.current(model)&&run===this.pickRun){
        if(guid)this.choose(guid,event.ctrlKey||event.metaKey||event.shiftKey);
        else if(!event.ctrlKey&&!event.metaKey&&!event.shiftKey)void this.select([]);
      }
    }catch(e){if(this.current(model))this.error.set(problem(e))}
  }
  async fitHit(event:MouseEvent){
    const run=this.modelRun;
    try{
      const guid=await this.viewer?.pick(event.clientX,event.clientY);
      if(this.current(run))await this.viewer?.fit(guid?[guid]:this.selection());
    }catch(e){if(this.current(run))this.error.set(problem(e))}
  }
  choose(guid:string,add=false){
    ++this.pickRun;
    const before=this.selection();
    void this.select(add?(before.includes(guid)?before.filter(id=>id!==guid):[...before,guid]):[guid]);
  }
  selectGroup(nodes:TreeNode[]){++this.pickRun;void this.select(nodes.map(node=>node.global_id))}
  allSelected(nodes:TreeNode[]){return nodes.length>0&&nodes.every(node=>this.selectedIds().has(node.global_id))}
  allHidden(nodes:TreeNode[]){
    const isolated=this.isolated(),hidden=this.hidden();
    return nodes.length>0&&nodes.every(node=>isolated?!isolated.has(node.global_id):hidden.has(node.global_id));
  }
  eyeLabel(name:string,nodes:TreeNode[]){return (this.allHidden(nodes)?'Mostrar ':'Ocultar ')+name}
  async toggleVisibility(nodes:TreeNode[]){
    if(this.visibilityBusy())return;
    const show=this.allHidden(nodes);
    await this.applyVisibility(show?'show':'hide',nodes.map(node=>node.global_id));
  }
  private async select(guids:string[]){
    const run=++this.selectionRun;
    const model=this.modelRun;
    this.selection.set(guids);this.selectionChanged.emit(guids.length>0);this.selectedElement.set(null);this.links.set([]);
    this.linksLoading.set(false);this.linkError.set('');
    this.material='';this.evidence='';
    const guid=this.selected();
    this.propertiesLoading.set(!!guid);
    if(guid){this.inspectorOpen.set(true);void this.loadLinks(guid)}
    const stillSelected=()=>this.current(model)&&run===this.selectionRun;
    try{
      const rendering=this.viewer?.select(guids);
      const properties=guid?this.api.page<IfcElement>('/documents/'+this.assetId+'/data',{q:guid,page_size:10}):undefined;
      const [,result]=await Promise.all([rendering,properties]);
      if(stillSelected()&&result)this.selectedElement.set(result.data.find(item=>item.global_id===guid)||null);
    }catch(e){if(stillSelected())this.error.set(problem(e))}
    finally{if(stillSelected())this.propertiesLoading.set(false)}
  }
  targetKind(){return this.targets.find(target=>target.id===this.targetId)?.file_type}
  async loadLinks(guid:string){
    if(!this.revisionId)return;
    this.linksLoading.set(true);this.linkError.set('');this.links.set([]);
    const run=this.selectionRun;
    try{
      const rows=await this.api.listAll<ComponentLink>('/revisions/'+this.revisionId+'/component-links',
        {ifc_asset_id:this.assetId,global_id:guid});
      if(!this.destroyed&&run===this.selectionRun)this.links.set(rows);
    }catch(e){if(!this.destroyed&&run===this.selectionRun)this.linkError.set(problem(e))}
    finally{if(!this.destroyed&&run===this.selectionRun)this.linksLoading.set(false)}
  }
  async createLink(element:IfcElement){
    if(this.linkSaving())return;
    this.linkSaving.set(true);this.linkError.set('');
    try{
      await this.api.post('/manufacturer/revisions/'+this.revisionId+'/component-links',
        {ifc_asset_id:this.assetId,ifc_global_id:element.global_id,target_asset_id:this.targetId,
          concept_code:this.code,material:this.material,unit:this.unit,evidence:this.evidence});
      if(this.selected()===element.global_id){this.evidence='';await this.loadLinks(element.global_id)}
    }catch(e){this.linkError.set(problem(e))}
    finally{this.linkSaving.set(false)}
  }
  async removeLink(link:ComponentLink){
    try{
      await this.api.remove('/manufacturer/revisions/'+this.revisionId+'/component-links/'+link.id);
      await this.loadLinks(this.selected());
    }catch(e){this.linkError.set(problem(e))}
  }
  async downloadLinked(link:ComponentLink){
    try{await this.api.download('/documents/'+link.document_id+'/download',link.document_name)}
    catch(e){this.linkError.set(problem(e))}
  }
  private async applyVisibility(mode:'show-all'|'show'|'hide'|'isolate',guids:string[]=[]){
    const run=this.modelRun;
    this.visibilityBusy.set(true);
    try{
      await this.viewer?.visibility(mode,guids);
      if(!this.current(run))return;
      const isolated=this.isolated();
      if(mode==='show-all'){this.hidden.set(new Set());this.isolated.set(null);return}
      if(mode==='isolate'){this.isolated.set(new Set(guids));return}
      const next=new Set(isolated||this.hidden());
      for(const guid of guids){
        const include=isolated?mode==='show':mode==='hide';
        if(include)next.add(guid);else next.delete(guid);
      }
      if(isolated)this.isolated.set(next);else this.hidden.set(next);
    }catch(e){if(this.current(run))this.error.set(problem(e))}
    finally{if(this.current(run))this.visibilityBusy.set(false)}
  }
  async perform(mode:'fit'|'show'|'isolate'|'hide'|'reset'){
    if(this.visibilityBusy())return;
    const run=this.modelRun;
    try{
      if(mode==='fit')await this.viewer?.fit(this.selection());
      else if(mode==='show')await this.applyVisibility('show-all');
      else if(mode==='reset'){
        ++this.pickRun;
        await this.applyVisibility('show-all');
        if(!this.current(run))return;
        this.cut.set(false);
        await this.viewer?.section(null);
        if(!this.current(run))return;
        await this.select([]);
        if(this.current(run))await this.viewer?.view('iso');
      }else await this.applyVisibility(mode,this.selection());
    }catch(e){if(this.current(run))this.error.set(problem(e))}
  }
  clearSelection(){++this.pickRun;void this.select([])}
  async changeView(event:Event){
    const value=(event.target as HTMLSelectElement).value;
    if(value!=='iso'&&value!=='front'&&value!=='top'&&value!=='side')return;
    const run=this.modelRun;
    try{await this.viewer?.view(value)}
    catch(e){if(this.current(run))this.error.set(problem(e))}
  }
  async fullscreen(workspace:HTMLElement){
    try{
      if(document.fullscreenElement===workspace)await document.exitFullscreen();
      else await workspace.requestFullscreen();
    }catch(e){if(!this.destroyed)this.error.set(problem(e))}
  }
  toggleCut(){this.cut.update(value=>!value);void this.updateCut()}
  adjustCut(event:Event){this.cutHeight=Number((event.target as HTMLInputElement).value);void this.updateCut()}
  private async updateCut(){
    const run=this.modelRun;
    try{await this.viewer?.section(this.cut()?this.cutHeight:null)}
    catch(e){if(this.current(run))this.error.set(problem(e))}
  }
  ngOnDestroy(){this.destroyed=true;this.download?.abort();this.viewer?.dispose()}
}
