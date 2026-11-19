/** Strict two-position selection with legacy commercial-UUID URL support. */
export const MAX_COMPARISON_ITEMS=2 as const;
export type SolutionKey=`g:${string}`|`p:${string}`;
const UUID=/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;

export function normalizeComparisonKey(input:string):SolutionKey|null {
  const raw=input.trim();
  const prefix=raw.includes(':')?raw.split(':',1)[0]:'p';
  const id=raw.includes(':')?raw.slice(raw.indexOf(':')+1):raw;
  return (prefix==='g'||prefix==='p')&&UUID.test(id)?`${prefix}:${id.toLowerCase()}` as SolutionKey:null;
}
export function normalizeComparisonIds(ids:readonly string[]):SolutionKey[]{
  const result:SolutionKey[]=[];
  for(const id of ids){
    const key=normalizeComparisonKey(id);
    if(key&&!result.includes(key)&&result.length<MAX_COMPARISON_ITEMS)result.push(key);
  }
  return result;
}

