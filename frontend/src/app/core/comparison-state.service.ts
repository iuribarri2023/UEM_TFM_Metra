import {Injectable,computed,signal} from '@angular/core';
import {MAX_COMPARISON_ITEMS,normalizeComparisonKey,normalizeComparisonIds,SolutionKey} from './comparison-selection';
export {MAX_COMPARISON_ITEMS,normalizeComparisonKey,normalizeComparisonIds} from './comparison-selection';
export type {SolutionKey} from './comparison-selection';

type Slots=[SolutionKey|null,SolutionKey|null];
/** A and B are fixed slots. Removing A does not silently move B. */
@Injectable({providedIn:'root'})
export class ComparisonStateService {
  readonly slots=signal<Slots>([null,null]);
  readonly items=computed(()=>this.slots().filter((key):key is SolutionKey=>key!==null));
  restore(value:string){
    const normalized=normalizeComparisonIds(value.split(','));
    this.slots.set([normalized[0]||null,normalized[1]||null]);
  }
  add(input:string):'added'|'already'|'full'|'invalid'{
    const key=normalizeComparisonKey(input);
    if(!key)return 'invalid';
    if(this.items().includes(key))return 'already';
    const index=this.slots().findIndex(item=>item===null);
    if(index<0)return 'full';
    return this.replace(index,key)?'added':'invalid';
  }
  replace(index:number,input:string):boolean{
    const key=normalizeComparisonKey(input);
    if(!key||index<0||index>=MAX_COMPARISON_ITEMS)return false;
    const next:Slots=[...this.slots()];
    if(next.some((item,slot)=>item===key&&slot!==index))return false;
    next[index]=key;this.slots.set(next);return true;
  }
  remove(input:string){
    const key=normalizeComparisonKey(input);
    this.slots.update(slots=>slots.map(item=>item===key?null:item) as Slots);
  }
  clearSlot(index:number){
    if(index<0||index>=MAX_COMPARISON_ITEMS)return;
    this.slots.update(slots=>slots.map((item,i)=>i===index?null:item) as Slots);
  }
  swap(){
    if(this.items().length!==2)return;
    this.slots.update(slots=>[slots[1],slots[0]]);
  }
  clear(){this.slots.set([null,null]);}
  toQuery(){return this.items().join(',');}
}
