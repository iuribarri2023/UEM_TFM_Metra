import {Component} from '@angular/core';
import {PortalLayoutComponent} from './portal-layout.component';
@Component({standalone:true,imports:[PortalLayoutComponent],template:'<app-portal-layout kind="admin" />'})
export class AdminLayoutComponent{}
