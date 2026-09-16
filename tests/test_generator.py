from playwright.sync_api import sync_playwright, expect
from test_import import ROOT, load_site, encrypt_download


def test_offline_generator_download_and_roundtrip(tmp_path):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(accept_downloads=True)
        page=context.new_page()
        load_site(page)
        page.get_by_role('button',name='Create an onward file',exact=True).click()
        page.get_by_role('button',name='Edit document title',exact=True).click()
        page.get_by_label('Document title',exact=True).fill('PRIVATE-DRAFT-MUST-NOT-BE-IN-GENERATOR')
        page.get_by_role('button',name='Save changes',exact=True).click()
        link=page.get_by_role('link',name='DOWNLOAD THE GENERATOR',exact=True)
        expect(link).to_be_visible(timeout=1500)
        with page.expect_download() as download:
            link.click()
        generator=tmp_path/'onward-generator.html'
        download.value.save_as(generator)
        assert download.value.suggested_filename=='onward-generator.html'
        html=generator.read_text()
        assert (ROOT/'LICENSE').read_text().strip() in html
        assert (ROOT/'licenses/SourceSerif4-OFL.txt').read_text().strip() in html
        assert '© 2014 - 2021 Adobe Systems Incorporated' in html
        assert 'PRIVATE-DRAFT-MUST-NOT-BE-IN-GENERATOR' not in html
        expect(page.locator('.editor-title')).to_have_text('PRIVATE-DRAFT-MUST-NOT-BE-IN-GENERATOR')
        context.set_offline(True)
        offline=context.new_page()
        errors=[]; requests=[]
        offline.on('pageerror',lambda e:errors.append(str(e)))
        offline.on('request',lambda r:requests.append(r.url) if r.url.startswith('http') else None)
        offline.goto(generator.as_uri())
        expect(offline.locator('#onward-editor')).to_be_visible()
        for width in [1440,390]:
            offline.set_viewport_size({'width':width,'height':1000})
            for theme in ['light','dark']:
                offline.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
                assert offline.evaluate('document.documentElement.scrollWidth<=innerWidth')
                offline.screenshot(path=str(ROOT/f'notes/screenshots/generator-{width}-{theme}.png'))
        offline.get_by_role('button',name='Edit document title',exact=True).click()
        offline.get_by_label('Document title',exact=True).fill('Created entirely offline')
        offline.get_by_role('button',name='Save changes',exact=True).click()
        result=tmp_path/'offline-created.html'
        encrypted=encrypt_download(offline,result)
        assert (ROOT/'LICENSE').read_text().strip() in encrypted
        assert 'Created entirely offline' not in encrypted
        # Downloading another clean generator also works without the hosted site.
        with offline.expect_download() as again:
            offline.get_by_role('link',name='DOWNLOAD THE GENERATOR',exact=True).click()
        second=tmp_path/'generator-copy.html'
        again.value.save_as(second)
        assert 'Created entirely offline' not in second.read_text()
        offline.goto(second.as_uri())
        expect(offline.locator('#onward-editor')).to_be_visible()
        recipient=context.new_page()
        recipient.goto(result.as_uri())
        recipient.locator('#password').fill('A long opening phrase 123')
        recipient.locator('#unlock').click()
        expect(recipient.locator('#document')).to_contain_text('Created entirely offline')
        assert not errors
        assert not requests
        browser.close()
