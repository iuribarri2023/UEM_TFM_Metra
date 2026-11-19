import {Component,Input} from '@angular/core';
import {FormsModule} from '@angular/forms';

export interface DeclaredInput {label:string;value:string;type:'number'|'text';unit:string;source:string}

export function editableValues(source:unknown):DeclaredInput[]{
  const data=source as {declared?:unknown}|null;
  if(!Array.isArray(data?.declared))return [];
  return data.declared.flatMap(row=>{
    if(!row||typeof row.label!=='string'||!['string','number'].includes(typeof row.value))return [];
    return [{label:row.label,value:String(row.value),type:typeof row.value==='number'?'number':'text',
      unit:typeof row.unit==='string'?row.unit:'',source:typeof row.source==='string'?row.source:''}];
  });
}

@Component({selector:'app-declared-value-editor',standalone:true,imports:[FormsModule],template:`
<section class="declared-editor">
  <h3>{{heading}}</h3>
  @for(row of rows;track row;let index=$index){
    <fieldset class="component"><legend>Magnitud {{index+1}}</legend>
      <div class="form-grid">
        <label>Nombre<input [(ngModel)]="row.label" maxlength="180" required></label>
        <label>Tipo<select [(ngModel)]="row.type"><option value="number">Número</option><option value="text">Texto</option></select></label>
        <label>Valor<input [(ngModel)]="row.value" [attr.inputmode]="row.type==='number'?'decimal':null" maxlength="500" required></label>
        <label>Unidad<input [(ngModel)]="row.unit" maxlength="60"></label>
        <label>Origen<input [(ngModel)]="row.source" maxlength="180"></label>
      </div>
      @if(!row.label.trim()||!row.value.trim()||invalidNumber(row)){<p class="small error">Introduce nombre y valor válidos para esta magnitud.</p>}
      <button type="button" class="text-link" (click)="rows.splice(index,1)">Retirar magnitud</button>
    </fieldset>
  }@empty{<p class="muted">Sin magnitudes editables.</p>}
  <button type="button" class="button button-ghost" [disabled]="rows.length>=100" (click)="add()">Añadir magnitud</button>
</section>`})
export class DeclaredValueEditorComponent {
  @Input({required:true}) heading='';
  @Input({required:true}) rows:DeclaredInput[]=[];
  invalidNumber(row:DeclaredInput){return row.type==='number'&&!Number.isFinite(Number(row.value.replace(',','.')))}
  add(){this.rows.push({label:'',value:'',type:'number',unit:'',source:''})}
}
