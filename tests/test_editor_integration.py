from pathlib import Path
import os
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]

def test_landing_opens_new_editor():
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        base=os.environ.get('ONWARD_TEST_URL',(ROOT/'site/index.html').as_uri())
        page.goto(base)
        assert '/login' not in page.url, 'Public Onward must not require a site password'
        page.get_by_role('button',name='Create an onward file',exact=True).click()
        expect(page.locator('#onward-editor')).to_be_visible()
        assert page.evaluate('typeof OnwardExport.createHTML')=='function'
        assert page.evaluate('typeof OnwardExport.previewHTML')=='function'
        for width in [1440,390]:
            page.set_viewport_size({'width':width,'height':1000})
            for theme in ['light','dark']:
                page.evaluate('(theme)=>document.documentElement.dataset.theme=theme',theme)
                for step in ['Edit','Encrypt']:
                    page.get_by_role('navigation',name='Document steps').get_by_role('button',name=step,exact=True).click()
                    expect(page.locator('.editor-toolbar .editor-eyebrow')).to_have_text('MAKE AN ONWARD FILE HERE. OR DOWNLOAD THE GENERATOR FOR 100% OFFLINE CREATION')
                    expect(page.get_by_role('button',name='Load existing file',exact=True)).to_be_visible()
                    expect(page.get_by_role('button',name='Open onward file',exact=True)).to_have_count(0)
                    expect(page.get_by_role('button',name='Preview',exact=True)).to_have_count(0)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.screenshot(path=str(ROOT/f'notes/screenshots/editor-copy-{width}-{theme}-{step}.png'))
        page.get_by_role('button',name='Load existing file',exact=True).click()
        expect(page.get_by_role('dialog',name='Load existing file',exact=True)).to_be_visible()
        assert not errors,errors
        browser.close()
