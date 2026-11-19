import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import {chromium} from 'playwright-core';

const base=process.env.METRA_URL||'http://127.0.0.1:8082';
const api=process.env.METRA_TEST_API||'http://127.0.0.1:8002';
const genericList=await (await fetch(api+'/api/v1/generic-solutions?q=E2E.IFC.GS001')).json();
const productList=await (await fetch(api+'/api/v1/products?q=E2E.IFC.P001')).json();
const generic=genericList.data.find(x=>x.code==='E2E.IFC.GS001');
const product=productList.data.find(x=>x.code==='E2E.IFC.P001');
assert(generic&&product,'Fixtures IFC ausentes de la base de ensayo');
const browser=await chromium.launch({timeout:20000,executablePath:process.env.CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const captures=process.env.METRA_CAPTURE_DIR;
  if(captures)await mkdir(captures,{recursive:true});
  async function capture(name){
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:900});
      const overflow=await page.evaluate(()=>({page:document.documentElement.scrollWidth,
        elements:[...document.querySelectorAll('body *')].map(el=>({tag:el.tagName,
          className:typeof el.className==='string'?el.className:'',right:el.getBoundingClientRect().right}))
          .filter(item=>item.right>innerWidth+2).sort((a,b)=>b.right-a.right).slice(0,8)}));
      assert(overflow.page<=width,name+' desborda a '+width+': '+JSON.stringify(overflow.elements));
      if(captures)await page.screenshot({path:join(captures,name+'-'+width+'.png'),fullPage:true});
    }
    await page.setViewportSize({width:1440,height:900});
  }
  page.on('pageerror',error=>console.error('PAGEERROR',error.message));
  page.on('console',message=>{if(message.type()==='error')console.error('CONSOLE',message.text())});
  page.on('response',response=>{if(response.status()>=400)console.error('HTTP',response.status(),response.url())});
  page.on('requestfailed',request=>console.error('FAILED',request.url(),request.failure()?.errorText));
  await page.route('**/api/v1/**',async route=>{
    const original=new URL(route.request().url());
    const upstream=await route.fetch({url:api+original.pathname+original.search});
    await route.fulfill({response:upstream});
  });
  await page.goto(base+'/generica/'+generic.id);
  await page.locator('.viewer-canvas canvas').waitFor({timeout:45000});
  await page.getByRole('button',{name:'Encuadrar'}).waitFor({state:'visible'});
  try{await page.waitForFunction(()=>document.querySelector('.bim-toolbar button')?.disabled===false,undefined,{timeout:20000})}
  catch(error){console.error('VIEWER ALERT',await page.locator('.bim-shell').innerText());throw error}
  await page.getByText('Árbol de componentes',{exact:false}).click();
  await page.getByRole('searchbox',{name:'Buscar componentes'}).fill('Panel de ensayo');
  await page.getByRole('button',{name:/^Panel de ensayo/}).click();
  await page.getByText('Selección ·',{exact:false}).waitFor();
  await page.getByText('Propiedades · Pset_METRA_Demo',{exact:true}).waitFor();
  await page.getByText('Propiedades · Pset_METRA_Demo',{exact:true}).click();
  await page.getByText('Thickness_mm').waitFor();
  const genericCanvas=await page.locator('.viewer-canvas canvas').elementHandle();
  await page.getByRole('button',{name:'Reiniciar',exact:true}).click();
  await page.getByRole('heading',{name:'Visión general',exact:true}).waitFor();
  const center=await genericCanvas.boundingBox();
  assert(center);
  await page.mouse.click(center.x+center.width/2,center.y+center.height/2);
  await page.getByText('Selección · Panel de ensayo',{exact:false}).waitFor();
  const source=generic.assets.find(asset=>asset.file_type==='IFC');
  assert.equal((await page.request.get(api+'/api/v1/assets/'+source.id+'/view')).headers()['x-metra-view-format'],'IFC_ORIGINAL');
  assert.equal((await page.request.get(api+'/api/v1/assets/'+source.id+'/download')).status(),404);
  await page.getByRole('button',{name:/^Ocultar Panel de ensayo/}).click();
  await page.getByRole('button',{name:/^Mostrar Panel de ensayo/}).waitFor();
  await page.getByRole('button',{name:'Mostrar todo',exact:true}).click();
  await page.getByRole('button',{name:/^Ocultar Panel de ensayo/}).waitFor();
  await page.getByRole('button',{name:'Corte horizontal',exact:true}).click();
  await page.getByRole('slider',{name:'Altura del corte'}).waitFor();
  await page.getByRole('button',{name:'Corte horizontal',exact:true}).click();
  await page.getByRole('navigation',{name:'Secciones de la ficha'}).getByRole('button',{name:'Prestaciones'}).click();
  assert(await genericCanvas.evaluate(el=>el===document.querySelector('.viewer-canvas canvas')));
  assert.equal(await page.locator('.bim-shell .bim-inspector').count(),0);
  await page.getByRole('navigation',{name:'Secciones de la ficha'}).getByRole('button',{name:'BIM',exact:true}).click();
  await page.getByText('Selección · Panel de ensayo',{exact:false}).waitFor();
  assert(await genericCanvas.evaluate(el=>el===document.querySelector('.viewer-canvas canvas')));

  await capture('ficha-generica');
  const modelSelector=page.getByLabel('Modelo activo');
  const choices=await modelSelector.locator('option').evaluateAll(options=>options.map(option=>option.value));
  assert(choices.length>=2);
  const active=await modelSelector.inputValue();
  await modelSelector.selectOption(choices.find(value=>value!==active));
  await page.waitForFunction(()=>document.querySelector('.bim-toolbar button')?.disabled===false);
  assert(await genericCanvas.evaluate(el=>!el.isConnected));
  assert.equal(await page.locator('.viewer-canvas canvas').count(),1);
  await page.getByRole('link',{name:'Volver al catálogo'}).click();
  await page.waitForURL(url=>url.pathname==='/catalogo');
  assert.equal(await page.locator('.viewer-canvas canvas').count(),0);
  assert.equal(await page.getByRole('alert').count(),0);
  await page.goto(base+'/producto/'+product.id);
  await page.getByText('El IFC está registrado, pero su visualización pública no está autorizada.').waitFor();
  await page.getByRole('navigation',{name:'Secciones de la ficha'}).getByRole('button',{name:'Economía'}).click();
  await page.getByRole('table').getByRole('row').filter({hasText:'test'}).getByRole('cell',{name:'1',exact:true}).waitFor();
  await page.getByRole('navigation',{name:'Secciones de la ficha'}).getByRole('button',{name:'Ambiente'}).click();
  await page.getByRole('table').getByRole('row').filter({hasText:'test'}).getByRole('cell',{name:'2',exact:true}).waitFor();
  assert.equal(await page.locator('.viewer-canvas canvas').count(),0);

  await page.goto(base+'/acceso');
  await page.getByLabel('Correo electrónico').fill('ifc-e2e@example.com');
  await page.getByLabel('Contraseña (mínimo 12 caracteres)').fill('IfcE2ePassword_1234');
  await page.getByRole('button',{name:'Continuar'}).click();
  await page.waitForURL(url=>url.pathname==='/admin',{timeout:15000});
  await page.getByRole('link',{name:'Revisión de productos'}).click();
  await page.getByRole('button',{name:'Revisión IFC de ensayo',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.bim-toolbar button')?.disabled===false);
  await capture('revision-administrativa');
  await page.goto(base+'/admin/ifc');
  await page.getByLabel('Buscar por código o nombre').fill('E2E.IFC.P001');
  await page.getByRole('button',{name:'Buscar'}).click();
  const review=page.getByRole('button',{name:'Revisar cambios'});
  assert(await review.isDisabled());
  await page.getByText('Selecciona al menos un IFC').waitFor();
  await page.getByRole('checkbox',{name:'Seleccionar E2E.IFC.P001'}).check();
  assert(await review.isDisabled());
  await page.getByText('No has modificado ningún permiso').waitFor();
  await page.getByLabel('Visualización pública propuesta').selectOption('allow');
  assert(await review.isDisabled());
  await page.getByText('Introduce al menos 10 caracteres de evidencia').waitFor();
  await page.getByLabel('Evidencia de autorización').fill('Cesión de visualización para ensayo en base desechable');
  assert(await review.isEnabled());
  await review.click();
  await page.getByRole('dialog',{name:'Revisión de permisos IFC'}).waitFor();
  await page.getByRole('button',{name:'Cancelar'}).click();
  assert.equal((await (await fetch(api+'/api/v1/products/'+product.id)).json()).data.published.bim_status,'PRIVATE');
  await page.route('**/api/v1/admin/ifc/permissions/bulk',route=>route.fulfill({status:403,
    contentType:'application/json',body:JSON.stringify({error:{code:'FORBIDDEN',message:'Sin permiso de ensayo',details:[]}})}),{times:1});
  await review.click();
  await page.getByRole('button',{name:'Confirmar y guardar'}).click();
  await page.getByRole('alert').getByText('403 · Sin permiso de ensayo').waitFor();
  assert(await page.getByRole('checkbox',{name:'Seleccionar E2E.IFC.P001'}).isChecked());
  await page.route('**/api/v1/admin/ifc/permissions/bulk',route=>route.fulfill({status:422,
    contentType:'application/json',body:JSON.stringify({error:{code:'VALIDATION',message:'Evidencia inválida de ensayo',details:[]}})}),{times:1});
  await review.click();
  await page.getByRole('button',{name:'Confirmar y guardar'}).click();
  await page.getByRole('alert').getByText('422 · Evidencia inválida de ensayo').waitFor();
  assert(await page.getByRole('checkbox',{name:'Seleccionar E2E.IFC.P001'}).isChecked());
  await review.click();
  let posts=0,submitted;
  page.on('request',request=>{if(request.method()==='POST'&&new URL(request.url()).pathname==='/api/v1/admin/ifc/permissions/bulk'){
    posts++;submitted=request.postDataJSON();
  }});
  await page.getByRole('button',{name:'Confirmar y guardar'}).dblclick();
  await page.getByRole('heading',{name:'Resultados'}).waitFor();
  assert.equal(posts,1);
  assert.equal(submitted.targets.length,1);
  assert.equal(submitted.targets[0].policy.public_view_allowed,true);
  assert.equal(submitted.targets[0].policy.public_download_allowed,false);
  assert.equal(submitted.targets[0].expected.public_download_allowed,false);
  await page.locator('tbody tr').filter({hasText:'E2E.IFC.P001'}).getByText('Autorizada').waitFor();
  assert.equal(await page.getByRole('alert').count(),0);
  const detail=await (await fetch(api+'/api/v1/products/'+product.id)).json();
  assert.equal(detail.data.published.bim_status,'VIEWABLE');
  const ifc=detail.data.published.assets.find(x=>x.file_type==='IFC');
  assert(ifc);
  assert.equal((await fetch(api+'/api/v1/assets/'+ifc.id+'/download')).status,404);
  await page.goto(base+'/producto/'+product.id);
  await page.locator('.viewer-canvas canvas').waitFor({timeout:45000});
  await page.waitForFunction(()=>document.querySelector('.bim-toolbar button')?.disabled===false,undefined,{timeout:45000});
  await page.getByText('Árbol de componentes',{exact:false}).click();
  await page.getByRole('searchbox',{name:'Buscar componentes'}).fill('Panel de ensayo');
  await page.getByRole('button',{name:/^Panel de ensayo/}).click();
  await page.getByText('Selección ·',{exact:false}).waitFor();
  await page.getByText('Propiedades · Pset_METRA_Demo',{exact:true}).waitFor();
  await capture('ficha-comercial');
  assert.equal(await page.getByRole('alert').count(),0);
  await page.goto(base+'/admin/ifc');
  await page.getByLabel('Buscar por código o nombre').fill('E2E.IFC.P001');
  await page.getByRole('button',{name:'Buscar'}).click();
  await page.getByRole('checkbox',{name:'Seleccionar E2E.IFC.P001'}).check();
  await page.getByLabel('Visualización pública propuesta').selectOption('deny');
  assert(await page.getByRole('button',{name:'Revisar cambios'}).isEnabled());
  await page.getByRole('button',{name:'Revisar cambios'}).click();
  await page.getByRole('button',{name:'Confirmar y guardar'}).click();
  await page.getByRole('heading',{name:'Resultados'}).waitFor();
  await page.locator('tbody tr').filter({hasText:'E2E.IFC.P001'}).getByText('Privada').first().waitFor();
  assert.equal((await (await fetch(api+'/api/v1/products/'+product.id)).json()).data.published.bim_status,'PRIVATE');
  await page.goto(base+'/producto/'+product.id);
  await page.getByText('El IFC está registrado, pero su visualización pública no está autorizada.').waitFor();
  console.log('IFC E2E real: revisión, concesión y revocación, geometría y descarga restringida OK');
}finally{await browser.close()}
