import {Component,Input} from '@angular/core';
/** Original document-system glyphs: structural frame (IFC), stepped estimate (BC3), footprint (EPD). */
@Component({selector:'app-document-glyph',standalone:true,template:`
<svg viewBox="0 0 44 44" width="26" height="26" fill="none" role="img" [attr.aria-label]="'Documento '+format" xmlns="http://www.w3.org/2000/svg">
  <path d="M9 4h19l8 8v28H9z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
  <path d="M28 4v8h8" stroke="currentColor" stroke-width="1.6"/>
  @switch(format){
    @case('IFC'){
      <path d="m15 22 7-4 8 4-8 5-7-5Zm0 0v10l7 5V27m8-5v10l-8 5" stroke="currentColor" stroke-width="1.3"/><path d="m15 27 7 4 8-4" stroke="currentColor" stroke-opacity=".5"/>
    }
    @case('BC3'){
      <path d="M14 19h17M14 24h17M14 29h17M20 18v15M26 18v15" stroke="currentColor" stroke-width="1.5"/><path d="M14 33h17" stroke="currentColor" stroke-width="2.3"/>
    }
    @case('EPD'){
      <path d="M17 32c-4-10 1-16 14-18 1 12-4 19-14 18Zm0 0 10-12" stroke="currentColor" stroke-width="1.6"/><path d="M17 31h-4" stroke="currentColor"/>
    }
    @default{<path d="M15 22h14M15 27h14M15 32h10" stroke="currentColor" stroke-width="1.5"/>}
  }
</svg>`,styles:[':host{display:inline-flex;flex:none;align-items:center;justify-content:center;color:inherit}']})
export class DocumentGlyphComponent {@Input() format='IFC'}
