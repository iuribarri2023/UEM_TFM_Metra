import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';
const base=process.env.METRA_URL||'http://127.0.0.1:8082';
const api=process.env.METRA_TEST_API||'http://127.0.0.1:8002';
const list=await (await fetch(api+'/api/v1/products?q=E2E.IFC.P001')).json();
const product=list.data.find(x=>x.code==='E2E.IFC.P001');
assert(product);
const detail=await (await fetch(api+'/api/v1/products/'+product.id)).json();
assert.equal(detail.data.published.bim_status,'PRIVATE');
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
  const page=await browser.newPage();
  await page.route('**/api/v1/**',async route=>{
    const url=new URL(route.request().url());
    await route.fulfill({response:await route.fetch({url:api+url.pathname+url.search})});
  });
  await page.goto(base+'/producto/'+product.id);
  await page.getByText('El IFC está registrado, pero su visualización pública no está autorizada.').waitFor();
  assert.equal(await page.locator('.viewer-canvas canvas').count(),0);
  assert.equal(await page.getByRole('alert').count(),0);
  console.log('Persistencia IFC tras reinicio: revocación pública conservada y visor oculto');
}finally{await browser.close()}
