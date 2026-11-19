/** Real-browser suite: requires running METRA + TWO published solutions. No mocks. */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {chromium} from 'playwright-core';

const base=process.env.METRA_URL||'http://127.0.0.1:8080';
const output=process.env.METRA_CAPTURE_DIR;
const executablePath=process.env.METRA_CHROMIUM_PATH||undefined;
const response=async path=>{
  const res=await fetch(new URL(path,base));
  assert.equal(res.status,200,`Error al consultar ${path}: ${res.status}`);
  return (await res.json()).data;
};

async function main(){
  const [generics,products]=await Promise.all([
    response('/api/v1/generic-solutions?page_size=100'),response('/api/v1/products?page_size=100')]);
  const firstGeneric=generics.find(g=>products.some(p=>p.subsystem_id===g.subsystem_id));
  assert(firstGeneric,'Se requiere genérica y comercial publicadas del mismo subsistema.');
  const product=products.find(p=>p.subsystem_id===firstGeneric.subsystem_id);
  const thirdGeneric=generics.find(g=>g.subsystem_id!==firstGeneric.subsystem_id);
  const options=[`g:${firstGeneric.id}`,`p:${product.id}`,...(thirdGeneric?[`g:${thirdGeneric.id}`]:[])];
  assert.ok(options.length>=2,'Se requieren dos fichas publicadas reales en la base de ensayo.');
  const first=options[0],second=options[1],third=options[2];
  if(output)await mkdir(resolve(output),{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath,args:['--no-sandbox','--disable-dev-shm-usage']});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(new URL(`/comparar?ids=${encodeURIComponent(first+','+second)}`,base).href,{waitUntil:'networkidle'});
    await page.locator('.compare-matrix').first().waitFor({state:'attached'});
    assert.equal(await page.locator('.compare-pickers:not(.compare-context) select').count(),2,'Deben existir A y B, nunca C');
    assert.equal(await page.locator('.compare-section').count(),7);
    assert.equal(await page.locator('.compare-pickers:not(.compare-context) select').nth(0).inputValue(),first);
    assert.equal(await page.locator('.compare-pickers:not(.compare-context) select').nth(1).inputValue(),second);
    await page.getByRole('button',{name:/Intercambiar/}).click();
    assert.equal(await page.locator('.compare-pickers:not(.compare-context) select').nth(0).inputValue(),second);
    await page.getByLabel('Mostrar solo diferencias').check();
    assert.equal(await page.getByLabel('Mostrar solo diferencias').isChecked(),true);
    await page.getByRole('button',{name:/Intercambiar/}).click();
    for(const width of [1440,1280,768,390]){
      await page.setViewportSize({width,height:900});
      await page.waitForTimeout(100);
      const outerWidth=await page.evaluate(()=>document.documentElement.scrollWidth-window.innerWidth);
      assert.ok(outerWidth<=2,`Desbordamiento horizontal de ${outerWidth}px a ${width}px`);
      if(output)await page.screenshot({path:resolve(output,`compare-${width}.png`),fullPage:true});
    }
    await page.getByRole('button',{name:'Retirar A'}).click();
    assert.equal(await page.locator('.compare-pickers:not(.compare-context) select').nth(0).inputValue(),'');
    assert.equal(await page.locator('.compare-pickers:not(.compare-context) select').nth(1).inputValue(),second,
      'Retirar A no debe mover B');
    if(third){
      await page.goto(new URL(`/comparar?ids=${encodeURIComponent(first+','+second+','+third)}`,base).href,{waitUntil:'networkidle'});
      await page.locator('.compare-matrix').first().waitFor({state:'attached'});
      assert.equal(await page.locator('.compare-pickers:not(.compare-context) select').nth(0).inputValue(),first);
      assert.equal(await page.locator('.compare-pickers:not(.compare-context) select').nth(1).inputValue(),second);
      assert.ok(!page.url().includes(encodeURIComponent(third)),'URL antigua debe truncarse a dos');
    }
    await page.getByRole('button',{name:'Limpiar'}).click();
    assert.equal(await page.locator('.compare-matrix').count(),0);
    assert.equal(await page.locator('.compare-pickers:not(.compare-context) select').count(),2);
    await page.goto(new URL(`/comparar?ids=${encodeURIComponent(first+','+third)}`,base).href);
    await page.getByRole('status').filter({hasText:'mismo sistema y subsistema'}).waitFor();
    assert.equal(await page.locator('.compare-matrix').count(),0);
    assert.deepEqual(errors,[],'Errores JS durante la comparación');
    console.log('PASS: comparador real en Chromium, matriz, dos posiciones, diferencia, intercambio, borrado, URL y responsive.');
  }finally{await browser.close()}
}
main().catch(error=>{console.error('FAIL E2E:',error);process.exitCode=1});
