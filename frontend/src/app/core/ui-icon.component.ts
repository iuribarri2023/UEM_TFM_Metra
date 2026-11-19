import {Component,Input} from '@angular/core';

const PATHS={
  overview:'M4 4h16v16H4z M4 10h16 M10 10v10',
  properties:'M5 6h14 M5 12h14 M5 18h14 M9 4v4 M15 10v4 M10 16v4',
  layers:'m12 3 9 5-9 5-9-5z M3 12l9 5 9-5 M3 16l9 5 9-5',
  cube:'m12 3 8 4.5v9L12 21l-8-4.5v-9z M4 7.5l8 4.5 8-4.5 M12 12v9',
  costs:'M4 19V5h16 M8 15v-3 M12 15V8 M16 15v-5 M20 15V7',
  environment:'M5 19c0-8 6-13 14-14 0 8-5 14-14 14z M5 19l8-8',
  document:'M6 3h8l4 4v14H6z M14 3v5h4 M9 13h6 M9 17h6',
  history:'M3 12a9 9 0 1 0 3-7 M3 4v5h5 M12 7v5l4 2',
  fit:'M9 4H4v5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5 M10 12h4 M12 10v4',
  eye:'M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  hidden:'M3 3l18 18 M10 6c7-1 12 6 12 6a17 17 0 0 1-4 4 M6 8a19 19 0 0 0-4 4c3 5 7 7 12 6',
  isolate:'M4 9V4h5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5 M9 9h6v6H9z',
  section:'m3 14 9 5 9-5 M3 9l9 5 9-5-9-5z M3 19l9 5 9-5',
  clear:'M6 6l12 12 M18 6 6 18',
  fullscreen:'M8 3H3v5 M16 3h5v5 M21 16v5h-5 M8 21H3v-5',
  arrow:'m9 5 7 7-7 7',
  down:'m5 9 7 7 7-7',
  team:'M7 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M2 20v-2c0-3 2-4 5-4s5 1 5 4v2 M16 6a3 3 0 1 1 0 6 M15 14c4 0 7 1 7 4v2',
  grid:'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  table:'M3 5h18v14H3z M3 10h18 M3 15h18 M9 10v9',
} as const;
export type UiIcon=keyof typeof PATHS;

@Component({selector:'app-ui-icon',standalone:true,template:`
<svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
  stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path [attr.d]="paths[name]"/></svg>`,
styles:[':host{display:inline-flex;align-items:center;justify-content:center;flex:none}']})
export class UiIconComponent {
  @Input({required:true}) name!:UiIcon;
  readonly paths=PATHS;
}
