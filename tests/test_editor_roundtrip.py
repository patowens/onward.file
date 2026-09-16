"""Real editor -> real cryptography -> file:// offline recipient. No export mocks."""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]

def test_edit_encrypt_download_offline(tmp_path):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        base=os.environ.get('ONWARD_TEST_URL',(ROOT/'site/index.html').as_uri())
        page.goto(base)
        assert '/login' not in page.url, 'Public Onward must not require a site password'
        page.get_by_role('button',name='Create an onward file',exact=True).click()
        outbound=[]
        page.on('request',lambda request: outbound.append(request.url) if request.url.startswith(('http://','https://')) else None)
        page.get_by_role('button',name='Edit document title',exact=True).click()
        page.get_by_label('Document title',exact=True).fill('Roundtrip family instructions\nKeep this safe')
        page.get_by_role('button',name='Save changes',exact=True).click()
        page.get_by_role('button',name='Edit row Email',exact=True).click()
        page.get_by_label('Password',exact=True).fill('PRIVATE-ROW-ROUNDTRIP-9517')
        page.get_by_label('Instruction',exact=True).fill('PRIVATE-INSTRUCTION-ROUNDTRIP-2831')
        page.get_by_role('button',name='Save changes',exact=True).click()
        page.get_by_role('navigation',name='Document steps').get_by_role('button',name='Encrypt',exact=True).click()
        page.get_by_label('Password',exact=True).fill('Roundtrip unlock phrase 7951')
        page.get_by_label('Confirm password',exact=True).fill('Roundtrip unlock phrase 7951')
        page.get_by_role('button',name='Encrypt and continue',exact=True).click()
        with page.expect_download() as info:
            page.get_by_role('button',name='Download onward file',exact=True).click()
        target=tmp_path/'onward.html'
        info.value.save_as(target)
        html=target.read_text()
        for secret in ['Roundtrip family instructions','PRIVATE-ROW-ROUNDTRIP-9517','PRIVATE-INSTRUCTION-ROUNDTRIP-2831','Roundtrip unlock phrase 7951']:
            assert secret not in html
        # An edit after a successful real export invalidates the prepared download.
        page.get_by_role('button',name='Back to Encrypt',exact=True).click()
        page.get_by_role('button',name='Back to Edit',exact=True).click()
        page.get_by_role('button',name='Edit document title',exact=True).click()
        page.get_by_label('Document title',exact=True).fill('A changed document')
        page.get_by_role('button',name='Save changes',exact=True).click()
        expect(page.get_by_role('navigation',name='Document steps').get_by_role('button',name='Download',exact=True)).to_be_disabled()
        context.set_offline(True)
        recipient=context.new_page()
        recipient.on('pageerror',lambda e:errors.append(str(e)))
        recipient.goto(target.as_uri())
        recipient.locator('#password').fill('wrong password')
        recipient.locator('#unlock').click()
        expect(recipient.locator('#error')).not_to_be_empty()
        recipient.locator('#password').fill('Roundtrip unlock phrase 7951')
        recipient.locator('#unlock').click()
        expect(recipient.locator('#document')).to_contain_text('Roundtrip family instructions')
        expect(recipient.locator('#document')).to_contain_text('PRIVATE-INSTRUCTION-ROUNDTRIP-2831')
        recipient.locator('#lock').click()
        expect(recipient.locator('#document')).to_be_empty()
        assert not outbound,outbound
        assert not errors,errors
        browser.close()
