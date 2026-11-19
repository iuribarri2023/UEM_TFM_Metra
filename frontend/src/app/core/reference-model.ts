export interface ReferencePart {
  label:string;
  value:number;
  unit?:string;
  quantity?:number;
  quantityUnit?:string;
}
export interface ReferenceModel {
  method:string;
  scope:string;
  functional_unit:string;
  subsystem:string;
  quantity:number;
  total:number;
  currency?:string;
  location?:string;
  period?:string;
  unit?:string;
  indicator?:string;
  items?:{label:string; subtotal:number; quantity:number;unit:string}[];
  modules?:{module:string;value:number}[];
  additional?:{label:string;value:number;unit:string;module:string}[];
}

export function referenceOf(value:unknown):ReferenceModel|null {
  if(!value||typeof value!=='object')return null;
  const model=(value as {reference?:ReferenceModel}).reference;
  return model?.method&&Number.isFinite(model.total)?model:null;
}

export function referenceParts(model:ReferenceModel):ReferencePart[] {
  return model.items?.map(x=>({label:x.label,value:x.subtotal,unit:model.currency,
    quantity:x.quantity,quantityUnit:x.unit}))??model.modules?.map(x=>({
      label:x.module,value:x.value,unit:model.unit
    }))??[];
}

export function comparableReference(a:ReferenceModel,b:ReferenceModel):boolean {
  const keys:(keyof ReferenceModel)[]=['method','scope','subsystem','functional_unit','quantity',
    'currency','location','period','unit','indicator'];
  return Boolean(a.method&&a.scope&&a.subsystem&&a.functional_unit&&a.quantity>0&&
    keys.every(key=>a[key]===b[key]) &&
    JSON.stringify(a.modules?.map(row=>row.module))===JSON.stringify(b.modules?.map(row=>row.module)));
}
