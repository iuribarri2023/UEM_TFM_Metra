import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {join} from 'node:path';
import {chromium} from 'playwright-core';

const browser=await chromium.launch({
  executablePath:process.env.CHROMIUM_EXECUTABLE,
  args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle',
        '--use-angle=swiftshader','--enable-unsafe-swiftshader']
});
try {
  const base=process.env.METRA_URL || 'http://localhost:8080';
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const captures=process.env.METRA_CAPTURE_DIR;
  if(captures)await mkdir(captures,{recursive:true});
  const capture=async name=>{
    if(captures)await page.screenshot({path:join(captures,name+'.png'),fullPage:true});
  };
  await page.goto(base+'/catalogo?q=Panel%20BIM');
  await page.getByRole("link",{name:"Panel BIM de ensayo",exact:true}).waitFor();
  for(const width of [1440,1280,768,390]){
    await page.setViewportSize({width,height:900});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,
      "El catálogo desborda a "+width+" px");
    await capture("catalogo-"+width);
  }
  await page.setViewportSize({width:1440,height:900});
  await page.getByRole('searchbox',{name:'Buscar soluciones'}).count().then(async count=>{
    if(count)await page.getByRole('searchbox',{name:'Buscar soluciones'}).fill('Panel BIM');
    else await page.getByLabel('Buscar soluciones').fill('Panel BIM');
  });
  await page.getByRole('button',{name:'Buscar',exact:true}).click();
  await page.waitForURL(url=>url.searchParams.get('q')==='Panel BIM');
  await page.reload();
  await page.getByRole('link',{name:'Panel BIM de ensayo',exact:true}).click();
  await page.getByRole('heading',{name:'Panel BIM de ensayo'}).waitFor();
  await page.getByRole('button',{name:'Encuadrar'}).waitFor();
  await page.locator('.viewer-canvas canvas').waitFor({timeout:45000});
  await page.waitForFunction(()=>document.querySelector('.bim-toolbar button')?.disabled===false,undefined,{timeout:45000});
  await capture('ficha-generica-ifc');
  const canvas=await page.locator('.viewer-canvas canvas').elementHandle();
  await page.getByRole('button',{name:'Prestaciones',exact:true}).click();
  await page.getByRole('heading',{name:'Prestaciones'}).waitFor();
  assert.equal(await canvas.evaluate(el=>el===document.querySelector('.viewer-canvas canvas')),true);
  await page.getByText('Árbol de componentes',{exact:false}).click();
  await page.getByRole('searchbox',{name:'Buscar componentes'}).fill('Panel de ensayo');
  await page.getByRole('button',{name:/^Panel de ensayo/}).click();
  await page.getByText('Selección · Panel de ensayo',{exact:false}).waitFor();
  await capture('ficha-generica-seleccion');
  await page.getByRole('button',{name:'Aislar',exact:true}).click();
  await page.getByRole('button',{name:'Mostrar todo',exact:true}).click();
  await page.getByRole('button',{name:'Documentos',exact:true}).click();
  const download=await page.getByRole('link',{name:'Descargar original'}).getAttribute('href');
  const response=await page.request.get(new URL(download,base).href);
  assert.equal(response.status(),200);
  assert.match((await response.body()).toString(),/ISO-10303-21/);
  assert.equal(await page.getByRole('alert').count(),0);
  console.log('Catálogo, búsqueda, carga IFC, selección, pestañas y descarga: OK');
} finally {
  await browser.close();
}
