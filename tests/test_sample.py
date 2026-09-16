from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_import import load_site, ROOT

PASSWORD = 'super-secret-only-mary-knows'
MESSAGE = 'Mary, this file contains account details and passwords.\nYou have the password with your others.'

def test_sample_modal_download_offline(tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        load_site(page)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        link = page.get_by_role('link', name='Try it out', exact=True)
        link.click()
        dialog = page.get_by_role('dialog', name='Try it out', exact=True)
        expect(dialog).to_be_visible(timeout=1500)
        expect(dialog).to_contain_text('An onward file is a downloadable, 100% self contained and encrypted secret store. Download this example and try it out.')
        expect(dialog.locator('blockquote')).to_have_text('“' + MESSAGE + '”')
        expect(dialog).to_contain_text('Password: ' + PASSWORD)
        for width in [1440,390,320]:
            page.set_viewport_size({'width':width,'height':900})
            for theme in ['light','dark']:
                page.evaluate('(theme)=>document.documentElement.dataset.theme=theme',theme)
                assert dialog.evaluate('d=>d.scrollWidth<=d.clientWidth')
                box=dialog.bounding_box()
                assert box['x']>=0 and box['x']+box['width']<=width
                page.screenshot(path=str(ROOT/f'notes/screenshots/sample-{width}-{theme}.png'))
        page.keyboard.press('Escape')
        expect(dialog).not_to_be_visible()
        expect(link).to_be_focused()
        link.click()
        with page.expect_download() as download:
            dialog.get_by_role('button',name='Download sample onward file.',exact=True).click()
        target=tmp_path/'sample.html'
        download.value.save_as(target)
        html=target.read_text()
        assert PASSWORD not in html
        assert 'example-only-123' not in html
        data=page.evaluate('async ({html,password})=>OnwardExport.openHTML(html,password)',{'html':html,'password':PASSWORD})
        assert data['title']==MESSAGE
        assert len(data['blocks'][0]['rows'])==3
        dialog.get_by_role('button',name='Close sample',exact=True).click()
        expect(link).to_be_focused()
        context.set_offline(True)
        recipient=context.new_page()
        recipient.on('pageerror',lambda e:errors.append(str(e)))
        requests=[]
        recipient.on('request',lambda r:requests.append(r.url) if r.url.startswith('http') else None)
        recipient.goto(target.as_uri())
        recipient.locator('#password').fill('incorrect-password')
        recipient.locator('#unlock').click()
        expect(recipient.get_by_role('alert')).to_contain_text('Unable to unlock')
        expect(recipient.locator('#document')).not_to_be_visible()
        recipient.locator('#password').fill(PASSWORD)
        recipient.locator('#unlock').click()
        expect(recipient.locator('#document')).to_contain_text('Mary, this file contains account details and passwords.')
        recipient.get_by_role('button',name='Reveal password',exact=True).first.click()
        expect(recipient.get_by_label('Stored password').first).to_have_value('example-only-123')
        assert not requests
        assert not errors
        browser.close()
