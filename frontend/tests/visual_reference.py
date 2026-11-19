"""Actual Chromium render of the HOME hero's own SVG and CSS (NOT Angular E2E).

Run from repository root: python frontend/tests/visual_reference.py
Screenshots carry 'static-preview' in their filename to distinguish them from app E2E.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
source=(ROOT/'frontend/src/app/features/home.component.ts').read_text()
start=source.index('<section class="home-hero"')
end=source.index('</section>',start)+len('</section>')
hero=source[start:end]
css='\n'.join((ROOT/f).read_text() for f in ['frontend/src/styles.css','frontend/src/workbench.css','frontend/src/app/features/home.component.css'])
html=f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>METRA · Vista estática de hero</title><style>{css}</style><body><div class="metra-home">{hero}</div></body></html>'
out=ROOT/'docs/screenshots';out.mkdir(exist_ok=True,parents=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'])
    for w in (1440,1280,768,390):
        page=browser.new_page(viewport={'width':w,'height':900},device_scale_factor=1)
        page.set_content(html,wait_until='load')
        page.screenshot(path=str(out/f'static-home-hero-{w}.png'),full_page=True)
        overflow=page.evaluate('document.documentElement.scrollWidth>window.innerWidth')
        svg=page.locator('.home-hero-visual svg').count()
        print(f'{w}px: overflow={overflow}; svg={svg}; screenshot=static-home-hero-{w}.png')
        assert not overflow, f'Document horizontally overflows at {w}px'
        assert svg==1
        page.close()
    browser.close()
