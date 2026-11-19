import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';

const base=process.env.METRA_URL||'http://127.0.0.1:8081';
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--disable-dev-shm-usage']});
try{
  const page=await browser.newPage();
  const id='11111111-1111-4111-8111-111111111111';
  let requests=[];let pending=true;let loggedIn=false;let fail=false;
  await page.route('**/api/v1/auth/refresh',route=>route.fulfill(loggedIn?{json:{data:{access_token:'test-token',role:'ADMIN'}}}:{status:401,json:{error:{code:'UNAUTHORIZED',message:'Sin sesión',details:[]}}}));
  await page.route('**/api/v1/auth/login',route=>{loggedIn=true;return route.fulfill({json:{data:{access_token:'test-token',role:'ADMIN'}}})});
  await page.route('**/api/v1/auth/me',route=>route.fulfill({json:{data:{id:'test',email:'admin@test.invalid',role:'ADMIN'}}}));
  await page.route('**/api/v1/admin/legacy/inventory**',route=>route.fulfill({json:{data:pending?[{
    id,code:'TEST.V3.001',name:'Panel histórico de prueba',kind:'commercial',manufacturer:'Prueba',
    classification:'TEST',status:'SUSPENDED',revision:1,updated_at:'2026-11-07T00:00:00Z',
    ifc_status:'VALID',has_bc3:false,has_epd:false,warnings:[]}]:[],meta:{page:1,page_size:20,total:pending?1:0}}}));
  await page.route('**/api/v1/admin/legacy/publications',async route=>{
    requests.push({method:route.request().method(),url:route.request().url(),body:route.request().postDataJSON(),headers:route.request().headers()});
    if(fail)return route.fulfill({status:403,json:{error:{code:'FORBIDDEN',message:'Permiso insuficiente',details:[]}}});
    await new Promise(resolve=>setTimeout(resolve,250));pending=false;
    await route.fulfill({json:{data:[{id,published:true}]}});
  });
  await page.goto(base+'/acceso');
  await page.getByLabel('Correo electrónico').fill('admin@test.invalid');
  await page.getByLabel('Contraseña (mínimo 12 caracteres)').fill('TestPassword_1234');
  await page.getByRole('button',{name:'Continuar'}).click();
  await page.goto(base+'/admin/legado');
  await page.getByRole('button',{name:'TEST.V3.001'}).waitFor();
  await page.getByRole('checkbox',{name:'Seleccionar Panel histórico de prueba'}).check();
  await page.getByLabel('Evidencia de autorización editorial').fill('Autorización editorial de ensayo');
  await page.getByLabel(/Confirmo que la evidencia/).check();
  await page.getByRole('button',{name:'Revisar fichas seleccionadas'}).click();
  const publish=page.getByRole('button',{name:'Confirmar y publicar'});
  await publish.click();
  assert.equal(await publish.isDisabled(),true);
  await page.getByText('Publicada',{exact:true}).waitFor();
  assert.equal(requests.length,1);
  assert.equal(requests[0].method,'POST');
  assert.equal(new URL(requests[0].url).pathname,'/api/v1/admin/legacy/publications');
  assert.match(requests[0].headers['content-type'],/application\/json/);
  assert.equal(requests[0].headers.authorization,'Bearer test-token');
  assert.deepEqual(requests[0].body,{kind:'commercial',ids:[id],evidence:'Autorización editorial de ensayo',confirmed:true,document_permissions:{}});
  assert.match(page.url(),/\/admin\/legado$/);
  assert.equal(await page.getByRole('checkbox',{name:'Seleccionar Panel histórico de prueba'}).count(),0);
  pending=true;fail=true;
  await page.reload();
  await page.getByRole('checkbox',{name:'Seleccionar Panel histórico de prueba'}).check();
  await page.getByLabel('Evidencia de autorización editorial').fill('Autorización editorial de ensayo');
  await page.getByLabel(/Confirmo que la evidencia/).check();
  await page.getByRole('button',{name:'Revisar fichas seleccionadas'}).click();
  await page.getByRole('button',{name:'Confirmar y publicar'}).click();
  await page.getByRole('alert').getByText('403 · Permiso insuficiente').waitFor();
  assert.equal(await page.getByRole('checkbox',{name:'Seleccionar Panel histórico de prueba'}).isChecked(),true);
  assert.equal(requests.length,2);
  console.log('Publicación Angular: POST único, payload, confirmación, carga, actualización y error 403 OK');
}finally{await browser.close()}
