import {Component,Input} from '@angular/core';

// Each silhouette describes a structural operation rather than a shared enclosure.
const FIGURES:Record<string,string[]> = {
  'EST.PIL':['M34 79V22l14-9 14 9v57l-14 8z M34 22l14 8 14-8 M48 30v57','M21 82l27 10 27-10'],
  'EST.VIG':['M10 46l63-22 12 8-63 23z M10 46v15l12 9 63-23V32 M22 55v15','M38 61v15m26-24v14'],
  'EST.MUR':['M16 75V34l51-18v41z M67 16l13 10v41L29 85 16 75 M29 85V44l51-18','M29 58l38-14m-38 28 38-14M45 39v41'],
  'EST.FOR':['M8 39l57-20 23 13-57 20z M8 39v12l23 14 57-20V32 M31 52v13','M18 57v11m12-3v12m14-17v12m14-17v12m14-17v12'],
  'ENV.FAC':['M15 70V32l51-18v38z M31 82V44l51-18v38z','M48 38v38m17-45v39M31 57l51-18m-51 30 51-18'],
  'ENV.CUB':['M9 54l39-32 39 32 M15 63l33-27 33 27 M23 70l25-20 25 20','M33 45l-4 6m19-17v9m15 2 4 6'],
  'ENV.VEN':['M20 74V28l56-13v46z M28 65V34l40-9v30z','M48 29v31m-20-10 40-10'],
  'INT.PAR':['M14 73V33l23-8v40z M58 82V42l23-8v40z','M37 29l21 13m-21 6 21 13m-21 6 21 13 M23 31v40m44-32v40'],
  'INT.TRA':['M20 78V30l48-16v48z M31 83V35l48-16v48z','M42 45v28m10-32v28m10-32v28m10-32v28'],
  'INT.SUE':['M7 55l52-20 29 15-52 20z M7 62l29 15 52-20','M24 49l29 15m-12-22 29 15M22 62l52-20'],
  'INT.TEC':['M11 36l57-18 17 12-57 18z M28 48v18m57-36v18M11 36v18','M11 54l17 12 57-18 M24 69l15 10 43-14'],
  'INT.PUE':['M20 83V26l42-10v57 M28 80V32l29-7v51','M57 25l20 15v41l-20-5 M68 55v4'],
  'MOD.BAN':['M12 39l42-21 28 15v39L42 87 12 71z M12 39l30 15 40-21 M42 54v33','M21 53l12 6v15 M51 58l21-9v16l-21 9z']
};
const SYSTEM_FALLBACK:Record<string,string>={EST:'EST.PIL',ENV:'ENV.FAC',INT:'INT.PAR',MOD:'MOD.BAN'};
@Component({selector:'app-architectural-glyph',standalone:true,template:`
<svg class="metra-glyph" viewBox="0 0 96 96" role="img" [attr.aria-label]="label" fill="none"
     stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
  @for(path of paths();track $index){
    <path [attr.d]="path" [attr.stroke-width]="$index===0?3:1.7" [attr.opacity]="$index===0?1:.62"/>
  }
</svg>`,styles:[':host{display:inline-flex;flex-shrink:0}.metra-glyph{display:block;width:100%;height:100%}']})
export class ArchitecturalGlyphComponent {
  @Input() system='';
  @Input() label='Diagrama arquitectónico esquemático';
  paths(){
    const code=this.system.toUpperCase().split('.').slice(0,2).join('.');
    return FIGURES[code]??FIGURES[SYSTEM_FALLBACK[code.split('.')[0]]]??FIGURES['ENV.FAC'];
  }
}
