import {Component,inject,OnInit,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {ApiService,problem} from '../core/api';
import {SubsystemTemplate} from '../core/canonical';

interface Counts {generic:number;commercial:number;fields:number;present:number;missing:number;invalid:number;unmapped:number}
interface Report {solutions:number;subsystems:Record<string,Counts>}
interface Version {id:string;version:number;fields:SubsystemTemplate['fields']}

@Component({standalone:true,imports:[FormsModule],template:`
  <section class="container content">
    <h1>Plantillas y calidad de datos</h1>
    <p>La cobertura cuenta declaraciones del inventario. Los valores estimados se presentan por separado.</p>
    @if(error()){<p role="alert" class="error">{{error()}}</p>}
    @if(report();as data){
      <p>{{data.solutions}} soluciones analizadas</p>
      <button class="button" (click)="download()">Exportar informe por ficha</button>
      <div class="technical-scroll"><table class="work-table">
        <thead><tr><th>Subsistema</th><th>Genéricas</th><th>Comerciales</th><th>Declarados</th><th>Ausentes</th><th>Inválidos</th><th>Sin mapear</th></tr></thead>
        <tbody>@for(code of codes();track code){@let row=data.subsystems[code];
          <tr><th scope="row"><button class="text-link" (click)="inspect(code)">{{code}}</button></th><td>{{row.generic}}</td><td>{{row.commercial}}</td><td>{{row.present}} / {{row.fields}}</td><td>{{row.missing}}</td><td>{{row.invalid}}</td><td>{{row.unmapped}}</td></tr>
        }</tbody>
      </table></div>
    }
    @if(template();as current){
      <h2>Plantilla {{current.code}}</h2>
      <label>Versión <select [ngModel]="version()" (ngModelChange)="version.set(+$event)">
        <option [value]="current.version">{{current.version}} · vigente</option>
        @for(item of versions();track item.id){@if(item.version!==current.version){<option [value]="item.version">{{item.version}}</option>}}
      </select></label>
      <ul>@for(field of fields();track field.code){<li>{{field.name_es||field.label||field.code}} · {{field.type}} · {{field.unit}} @if(field.required){· Obligatorio}</li>}</ul>
    }
  </section>
`})
export class AdminQualityComponent implements OnInit {
  private api=inject(ApiService);
  report=signal<Report|null>(null);error=signal('');codes=signal<string[]>([]);
  template=signal<SubsystemTemplate|null>(null);versions=signal<Version[]>([]);version=signal(0);
  async ngOnInit(){
    try{const report=await this.api.get<Report>('/admin/data-quality');this.report.set(report);this.codes.set(Object.keys(report.subsystems))}
    catch(e){this.error.set(problem(e))}
  }
  async inspect(code:string){
    try{
      const [template,versions]=await Promise.all([
        this.api.get<SubsystemTemplate>('/data-templates/'+code),
        this.api.listAll<Version>('/admin/templates/'+code+'/versions')]);
      this.template.set(template);this.versions.set(versions);this.version.set(template.version);
    }catch(e){this.error.set(problem(e))}
  }
  fields(){return this.versions().find(item=>item.version===this.version())?.fields??this.template()?.fields??[]}
  async download(){
    try{
      const result=await this.api.get('/admin/data-quality',{entries:'1'});
      const link=document.createElement('a');
      link.href=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
      link.download='metra-calidad-v4.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
    }catch(e){this.error.set(problem(e))}
  }
}
