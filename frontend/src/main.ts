import {bootstrapApplication} from '@angular/platform-browser';
import {provideRouter,withComponentInputBinding,withInMemoryScrolling} from '@angular/router';
import {provideHttpClient,withInterceptors} from '@angular/common/http';
import {APP_ROUTES} from './app/app.routes';
import {AppComponent} from './app/app.component';
import {authInterceptor} from './app/core/api';
bootstrapApplication(AppComponent,{providers:[provideRouter(APP_ROUTES,withComponentInputBinding(),withInMemoryScrolling({anchorScrolling:'enabled',scrollPositionRestoration:'enabled'})),provideHttpClient(withInterceptors([authInterceptor]))]})
  .catch(error=>console.error('No se pudo iniciar la aplicación',error));
