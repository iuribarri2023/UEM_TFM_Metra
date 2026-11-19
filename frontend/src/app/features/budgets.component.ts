import {Component,Input,OnChanges,inject,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {ApiService,problem} from '../core/api';

interface Budget{id:string;name:string;revision_id?:string}
interface Item{id?:string;code:string;description:string;unit:string;quantity:string;unit_price:string;total?:string}

@Component({selector:'app-budgets',standalone:true,imports:[FormsModule],template:`
<section class="panel">
  <h2>Presupuestos</h2>
  @if(editable){
    <form class="catalog-controls" (ngSubmit)="create()">
      <label>Nombre del presupuesto<input name="name" [(ngModel)]="name" maxlength="180" required></label>
      <button class="button" [disabled]="!name.trim()">Crear presupuesto</button>
    </form>
  }
  @if(error()){<p class="error" role="alert">{{error()}}</p>}
  @for(b of budgets();track b.id){
    <button class="text-link" [attr.aria-pressed]="selected()?.id===b.id" (click)="select(b)">{{b.name}}</button>
  }@empty{<p class="muted">Sin presupuestos disponibles.</p>}
  @if(selected();as budget){
    <div class="actions">
      <button class="button button-ghost" (click)="download(budget)">Exportar BC3</button>
      @if(canEdit(budget)){
        <label>Archivar presupuesto<input type="checkbox" [(ngModel)]="archiveConfirmed"></label>
        <button class="button button-ghost" [disabled]="!archiveConfirmed" (click)="archive(budget)">Confirmar archivo</button>
      }
    </div>
    <p><strong>Total · {{total()}}</strong></p>
    <div class="technical-scroll">
      <table><thead><tr><th>Código</th><th>Partida</th><th>Unidad</th><th>Cantidad</th><th>Precio</th><th>Importe</th>@if(canEdit(budget)){<th>Acciones</th>}</tr></thead>
        <tbody>@for(item of items();track item.id){
          <tr><td>{{item.code}}</td><td>{{item.description}}</td><td>{{item.unit}}</td><td>{{item.quantity}}</td><td>{{item.unit_price}}</td><td>{{item.total}}</td>
            @if(canEdit(budget)){<td><button class="text-link" (click)="edit(item)">Editar</button></td>}</tr>
        }</tbody>
      </table>
    </div>
    @if(canEdit(budget)){
      <form class="form-grid" (ngSubmit)="save(budget)">
        <label>Código<input name="code" [(ngModel)]="form.code" required></label>
        <label>Partida<input name="description" [(ngModel)]="form.description" required></label>
        <label>Unidad<input name="unit" [(ngModel)]="form.unit" required></label>
        <label>Cantidad<input name="quantity" inputmode="decimal" [(ngModel)]="form.quantity" required></label>
        <label>Precio unitario<input name="price" inputmode="decimal" [(ngModel)]="form.unit_price" required></label>
        <button class="button">{{form.id?'Guardar partida':'Añadir partida'}}</button>
        @if(form.id){
          <button class="button button-ghost" type="button" (click)="clear()">Nueva partida</button>
          <label>Confirmar retirada<input type="checkbox" [(ngModel)]="itemConfirmed" name="confirm"></label>
          <button class="button button-ghost" type="button" [disabled]="!itemConfirmed" (click)="remove(budget)">Retirar partida</button>
        }
      </form>
    }
    <button class="button button-ghost" [disabled]="page()<=1" (click)="loadItems(budget,page()-1)">Anterior</button>
    <button class="button button-ghost" [disabled]="page()*50>=count()" (click)="loadItems(budget,page()+1)">Siguiente</button>
  }
</section>`})
export class BudgetsComponent implements OnChanges {
  @Input() productId='';
  @Input() editable=false;
  @Input() draftId='';
  private api=inject(ApiService);
  budgets=signal<Budget[]>([]);selected=signal<Budget|null>(null);items=signal<Item[]>([]);
  total=signal('—');page=signal(1);count=signal(0);error=signal('');
  name='';archiveConfirmed=false;itemConfirmed=false;
  form:Item={code:'',description:'',unit:'m2',quantity:'1',unit_price:'0'};
  private listRun=0;private itemRun=0;
  path(){return this.productId?'/products/'+this.productId+'/budgets':'/budgets'}
  canEdit(b:Budget){return this.editable&&(!b.revision_id||b.revision_id===this.draftId)}
  async ngOnChanges(){this.selected.set(null);await this.load()}
  async load(){
    const run=++this.listRun;
    try{const rows=await this.api.listAll<Budget>(this.path());if(run===this.listRun)this.budgets.set(rows)}
    catch(e){if(run===this.listRun)this.error.set(problem(e))}
  }
  async create(){
    try{const b=await this.api.post<Budget>(this.path(),{name:this.name});this.name='';await this.load();await this.select(b)}
    catch(e){this.error.set(problem(e))}
  }
  async select(b:Budget){this.selected.set(b);this.clear();this.archiveConfirmed=false;await this.loadItems(b,1)}
  async loadItems(b:Budget,page:number){
    const run=++this.itemRun;
    try{
      const [items,totals]=await Promise.all([
        this.api.page<Item>('/budgets/'+b.id+'/items',{page,page_size:50}),
        this.api.get<{total:string}>('/budgets/'+b.id+'/totals')
      ]);
      if(run!==this.itemRun||this.selected()?.id!==b.id)return;
      this.items.set(items.data);this.total.set(totals.total);this.page.set(page);this.count.set(items.meta?.total||0);
    }catch(e){if(run===this.itemRun)this.error.set(problem(e))}
  }
  edit(item:Item){this.form={...item};this.itemConfirmed=false}
  clear(){this.form={code:'',description:'',unit:'m2',quantity:'1',unit_price:'0'};this.itemConfirmed=false}
  async save(b:Budget){
    const base='/budgets/'+b.id+'/items';
    try{
      if(this.form.id)await this.api.patch(base+'/'+this.form.id,this.form);
      else await this.api.post(base,this.form);
      this.clear();await this.loadItems(b,this.page());
    }catch(e){this.error.set(problem(e))}
  }
  async remove(b:Budget){
    if(!this.form.id||!this.itemConfirmed)return;
    try{await this.api.remove('/budgets/'+b.id+'/items/'+this.form.id);this.clear();await this.loadItems(b,1)}
    catch(e){this.error.set(problem(e))}
  }
  async archive(b:Budget){
    if(!this.archiveConfirmed)return;
    try{await this.api.remove('/budgets/'+b.id);this.selected.set(null);await this.load()}
    catch(e){this.error.set(problem(e))}
  }
  async download(b:Budget){try{await this.api.download('/budgets/'+b.id+'/export/bc3',b.name+'.bc3')}catch(e){this.error.set(problem(e))}}
}
