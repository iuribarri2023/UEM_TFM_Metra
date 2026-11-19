import {Component,Input,Output,EventEmitter,OnChanges} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {Asset} from '../core/api';

export interface DocumentPolicy {
  public_view_allowed:boolean;
  public_download_allowed:boolean;
  rights_evidence:string;
}

@Component({selector:'app-document-policy',standalone:true,imports:[FormsModule],template:`
<fieldset class="component">
  <legend>{{asset.original_name}} · {{asset.processing_status}}</legend>
  @if(asset.file_type==='IFC'){
    <label class="inline-check"><input type="checkbox" [(ngModel)]="view"
      [disabled]="asset.processing_status!=='VALID'&&!view" (ngModelChange)="emit()"> Visualización pública</label>
  }
  <label class="inline-check"><input type="checkbox" [(ngModel)]="download" (ngModelChange)="emit()"> Descarga pública</label>
  @if(grant()){
    <label>Evidencia de autorización<input [(ngModel)]="evidence" maxlength="2000" (ngModelChange)="emit()"></label>
  }
</fieldset>`})
export class DocumentPolicyComponent implements OnChanges {
  @Input({required:true}) asset!:Asset;
  @Output() policy=new EventEmitter<DocumentPolicy|null>();
  view=false;download=false;evidence='';
  ngOnChanges(){
    this.view=!!this.asset.public_view_allowed;
    this.download=!!this.asset.public_download_allowed;
    this.evidence='';
  }
  grant(){return this.view&&!this.asset.public_view_allowed||this.download&&!this.asset.public_download_allowed}
  emit(){
    const changed=this.view!==!!this.asset.public_view_allowed||this.download!==!!this.asset.public_download_allowed;
    this.policy.emit(changed?{public_view_allowed:this.view,public_download_allowed:this.download,
      rights_evidence:this.evidence.trim()}:null);
  }
}
