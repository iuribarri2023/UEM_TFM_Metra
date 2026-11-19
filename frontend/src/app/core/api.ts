import {CanonicalSolution,TemplateHighlight} from './canonical';
import {Injectable,inject,signal} from '@angular/core';
import {HttpClient,HttpInterceptorFn,HttpErrorResponse} from '@angular/common/http';
import {firstValueFrom,fromEvent,takeUntil} from 'rxjs';
export interface Envelope<T>{data:T;meta?:{page?:number;page_size?:number;total?:number;truncated?:boolean}}
export interface SessionTokens {access_token:string;role?:string;token_type?:string;expires_in?:number}
export interface UserIdentity {id?:string;email?:string;role:string;active?:boolean;manufacturer_id?:string}
export interface ManufacturerProfile {name:string;description:string;website:string|null;public_email:string|null;contact_public:boolean}
export interface ManufacturerNotification {id:string;event:string;message:string;read_at?:string|null}
export interface AuditEntry {id:string;at:string;action:string;entity:string;entity_id:string}
export interface Invitation {invitation_token:string}
/** Expresiones de prestaciones no verificadas: la API puede entregar distintos contratos por subsistema. */
export interface TechnicalDatum {value?:string|number|boolean|null;unit?:string;source_type?:string;verification_status?:string}
export interface DocumentExtraction {is_valid?:boolean;normalized?:Record<string,unknown>;warnings?:string[]}
export interface Asset {id:string;file_type:string;original_name:string;size:number;processing_status:string;public_download_allowed?:boolean;public_view_allowed?:boolean;thumbnail_available?:boolean;extraction?:DocumentExtraction}
export interface Revision {canonical?:CanonicalSolution;template_highlights?:TemplateHighlight[];id:string;product_id:string;number:number;status:string;name_es:string;template_version?:number;description:string;commercial_reference:string;functional_unit:string;technical_data:any;economic_data?:unknown;environmental_data?:unknown;bim_status?:string;generic_solution_ids:string[];assets:Asset[];rejection_reason?:string;parent_id?:string;created_at?:string;created_by?:string;message?:string}
export interface Product {id:string;code:string;subsystem_id:string;manufacturer_id:string;availability:string;published_revision_id?:string;published?:Revision;revisions?:Revision[];manufacturer?:{id:string;name:string;website?:string;public_email?:string}}
export interface Generic {canonical?:CanonicalSolution;template_highlights?:TemplateHighlight[];id:string;code:string;name_es:string;subsystem_id:string;archetype_id:string;status:string;technical_data:any;composition:any[];slots:any[];assets:Asset[];bim_status?:string;economic_data?:unknown;environmental_data?:unknown}
export interface Taxon {id:string;code:string;name_es:string;archived:boolean;system_id?:string;subsystem_id?:string}
export const authInterceptor:HttpInterceptorFn=(request,next)=>{
  const store=inject(SessionService);
  const headers:Record<string,string>={};
  if(store.token())headers['Authorization']='Bearer '+store.token();
  const csrf=document.cookie.match(/(?:^|;\s*)csrf=([^;]+)/);
  if(csrf)headers['X-CSRF-Token']=decodeURIComponent(csrf[1]);
  return next(request.clone({withCredentials:true,setHeaders:headers}));
};
@Injectable({providedIn:'root'})
export class SessionService {
  token=signal<string>('');role=signal<string>('');identity=signal<UserIdentity|null>(null);
  private http=inject(HttpClient);private restoring?:Promise<void>;
  setSession(data:SessionTokens){this.token.set(data.access_token);if(data.role)this.role.set(data.role)}
  restore():Promise<void>{if(!this.restoring)this.restoring=this.doRestore();return this.restoring}
  private async doRestore(){try{const a=await firstValueFrom(this.http.post<Envelope<SessionTokens>>('/api/v1/auth/refresh',{}));this.setSession(a.data);await this.me()}catch{this.token.set('');this.role.set('')}}
  async me(){const r=await firstValueFrom(this.http.get<Envelope<UserIdentity>>('/api/v1/auth/me'));this.identity.set(r.data);this.role.set(r.data.role)}
  async logout(){try{await firstValueFrom(this.http.post('/api/v1/auth/logout',{}))}catch{}this.token.set('');this.role.set('');this.identity.set(null)}
}
@Injectable({providedIn:'root'})
export class ApiService {
  private http=inject(HttpClient);
  get<T>(path:string,params:any={}){return firstValueFrom(this.http.get<Envelope<T>>('/api/v1'+path,{params})).then(r=>r.data)}
  list<T>(path:string,params:any={}){return firstValueFrom(this.http.get<Envelope<T[]>>('/api/v1'+path,{params})).then(r=>r.data)}
  page<T>(path:string,params:any={}){
    return firstValueFrom(this.http.get<Envelope<T[]>>('/api/v1'+path,{params}));
  }
  async listAll<T>(path:string,params:any={}):Promise<T[]> {
    const combined:T[]=[];
    for(let page=1;page<=30;page++){
      const r=await firstValueFrom(this.http.get<Envelope<T[]>>('/api/v1'+path,{params:{...params,page,page_size:100}}));
      combined.push(...r.data);
      if(r.data.length<100 || (r.meta?.total!==undefined && combined.length>=r.meta.total))break;
    }
    return combined;
  }
  post<T>(path:string,body:unknown){return firstValueFrom(this.http.post<Envelope<T>>('/api/v1'+path,body)).then(r=>r.data)}
  patch<T>(path:string,body:unknown){return firstValueFrom(this.http.patch<Envelope<T>>('/api/v1'+path,body)).then(r=>r.data)}
  remove(path:string){return firstValueFrom(this.http.delete('/api/v1'+path))}
  upload<T>(path:string,file:File,fields:Record<string,string>={}){const fd=new FormData();fd.append('file',file);for(const [key,value] of Object.entries(fields))fd.append(key,value);return firstValueFrom(this.http.post<Envelope<T>>('/api/v1'+path,fd)).then(r=>r.data)}
  async download(path:string,name:string){
    const bytes=await this.bytes(path);
    const url=URL.createObjectURL(new Blob([bytes]));
    const link=document.createElement('a');link.href=url;link.download=name;link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  bytes(path:string,abort?:AbortSignal){
    if(abort?.aborted)return Promise.reject(abort.reason);
    const response=this.http.get('/api/v1'+path,{responseType:'arraybuffer'});
    return firstValueFrom(abort?response.pipe(takeUntil(fromEvent(abort,'abort'))):response);
  }
}
/** Normaliza errores HTTP sin asumir que el cuerpo remoto es tipado. */
export function problem(e:unknown):string{
  if(e instanceof HttpErrorResponse){
    const payload=e.error as {error?:{details?:unknown;message?:unknown}}|null;
    const detail=payload?.error;
    const message=Array.isArray(detail?.details)&&detail.details.length
      ?detail.details.map((x:unknown)=>{
        if(typeof x==='string')return x;
        if(x!==null&&typeof x==='object'&&'msg' in x)return String(x.msg);
        return JSON.stringify(x);
      }).join(' · ')
      :detail?.message;
    if(typeof message==='string'&&message)return `${e.status} · ${message}`;
    const fallback:Record<number,string>={400:'Solicitud inválida',401:'Inicia sesión de nuevo',403:'No tienes permiso para publicar',405:'Método no permitido por la ruta',409:'La ficha ha cambiado o ya está decidida',422:'Revisa los datos del formulario',500:'Error interno del servidor'};
    return `${e.status||'Red'} · ${fallback[e.status]||'Error de conexión'}`;
  }
  return e instanceof Error?e.message:'Error inesperado';
}
