"""Local encrypted HTML reopening: real Chromium/WebCrypto, no export mocks."""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'A long opening phrase 123'
DATA = {'title': 'Imported\nfamily notes', 'blocks': [{'id': 'untrusted-block', 'title': 'Accounts', 'description': 'Keep safe', 'rows': [{'id': 'untrusted-row', 'item': 'Email', 'username': 'me', 'password': 'first\nsecond\r\nthird', 'instruction': 'Read\ncarefully'}]}]}


def load_site(page):
    base = os.environ.get('ONWARD_TEST_URL', (ROOT/'site/index.html').as_uri())
    page.goto(base)
    assert '/login' not in page.url, 'Public Onward must not require a site password'


def test_import_four_mebibyte_plaintext_roundtrip():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        load_site(page)
        result = page.evaluate('''async ({data,password}) => {
          data.blocks[0].rows[0].instruction = 'x'.repeat(4*1024*1024);
          const html = await OnwardExport.createHTML(data,password);
          const restored = await OnwardExport.openHTML(html,password);
          return {size:new Blob([html]).size, same:JSON.stringify(restored)===JSON.stringify(data)};
        }''', {'data':DATA,'password':PASSWORD})
        assert result['size'] < 10*1024*1024
        assert result['same']
        browser.close()


def test_import_api_roundtrip():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        load_site(page)
        result = page.evaluate('''async ({data,password}) => {
          const html = await OnwardExport.createHTML(data,password);
          return await OnwardExport.openHTML(html,password);
        }''', {'data': DATA, 'password': PASSWORD})
        assert result == DATA
        browser.close()


def test_import_rejects_unsupported_envelopes_and_inert_markup():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        load_site(page)
        outbound = []
        page.on('request', lambda r: outbound.append(r.url))
        result = page.evaluate('''async ({data,password}) => {
          const html = await OnwardExport.createHTML(data,password);
          const payload = html.match(/<script id="payload" type="application\\/json">(.*?)<\\/script>/s)[1];
          const env = JSON.parse(payload);
          const wrap = e => '<script id="payload" type="application/json">'+JSON.stringify(e)+'</script>';
          const variants = [wrap({...env,iterations:1}), wrap({...env,preview:true}),
            wrap({...env,salt:env.salt+'\\n'}), wrap({...env,iv:'AAAA'}),
            wrap({...env,ciphertext:'AAAA'}), wrap({...env,version:2}),
            wrap(env)+wrap(env), '<script id="payload" type="text/plain">'+payload+'</script>',
            'not html', wrap(null), 'x'.repeat(10*1024*1024+1),
            wrap(env)+'<template>'+wrap(env)+'</template>'];
          const accepted = [];
          for (let i=0;i<variants.length;i++) {
            try {await OnwardExport.openHTML(variants[i],password); accepted.push(i);} catch (_) {}
          }
          const malicious = '<img src="https://attacker.invalid/image" onerror="window.pwned=1">'+
            '<iframe src="https://attacker.invalid/frame"></iframe><link rel="stylesheet" href="https://attacker.invalid/style">'+
            '<script>window.pwned=1;fetch("https://attacker.invalid/script")</script>'+wrap(env);
          const restored = await OnwardExport.openHTML(malicious,password);
          // Authenticated but schema-invalid plaintext must also be rejected.
          const bytes = s => Uint8Array.from(atob(s),c=>c.charCodeAt(0));
          const base = await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);
          const key = await crypto.subtle.deriveKey({name:'PBKDF2',salt:bytes(env.salt),iterations:600000,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['encrypt']);
          const cipher = await crypto.subtle.encrypt({name:'AES-GCM',iv:bytes(env.iv)},key,new TextEncoder().encode(JSON.stringify({title:7,blocks:[]})));
          let invalidSchemaAccepted = false;
          try {await OnwardExport.openHTML(wrap({...env,ciphertext:btoa(String.fromCharCode(...new Uint8Array(cipher)))}),password); invalidSchemaAccepted=true;} catch (_) {}
          return {accepted, restored, pwned:!!window.pwned, invalidSchemaAccepted};
        }''', {'data': DATA, 'password': PASSWORD})
        assert result['accepted'] == []
        assert result['restored'] == DATA
        assert not result['pwned']
        assert not result['invalidSchemaAccepted']
        page.wait_for_timeout(150)
        assert not outbound
        browser.close()


def encrypt_download(page, target, password=PASSWORD):
    page.get_by_role('navigation', name='Document steps').get_by_role('button', name='Encrypt', exact=True).click()
    page.get_by_label('Password', exact=True).fill(password)
    page.get_by_label('Confirm password', exact=True).fill(password)
    page.get_by_role('button', name='Encrypt and continue', exact=True).click()
    with page.expect_download() as info:
        page.get_by_role('button', name='Download onward file', exact=True).click()
    info.value.save_as(target)
    return target.read_text()


def open_dialog(page, file, password=PASSWORD):
    page.get_by_role('button', name='Load existing file', exact=True).click()
    dialog = page.get_by_role('dialog', name='Load existing file', exact=True)
    dialog.get_by_label('Encrypted onward file', exact=True).set_input_files(file)
    dialog.get_by_label('File password', exact=True).fill(password)
    return dialog


def test_editor_reopen_edit_reexport_preserves_draft_on_failure(tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width':1440,'height':1000}, accept_downloads=True)
        page = context.new_page()
        load_site(page)
        page.get_by_role('button', name='Create an onward file', exact=True).click()
        outbound, errors = [], []
        page.on('request', lambda r: outbound.append(r.url))
        page.on('pageerror', lambda e: errors.append(str(e)))
        for step in ['Edit', 'Encrypt']:
            page.get_by_role('navigation', name='Document steps').get_by_role('button', name=step, exact=True).click()
            expect(page.get_by_role('button', name='Load existing file', exact=True)).to_be_enabled()
        page.get_by_role('button', name='Back to Edit', exact=True).click()
        page.get_by_role('button', name='Edit row Email', exact=True).click()
        secret = 'first line\nsecond line\nthird line'
        page.get_by_label('Password', exact=True).fill(secret)
        page.get_by_role('button', name='Save changes', exact=True).click()
        original = tmp_path / 'original.html'
        html = encrypt_download(page, original)
        original_data = page.evaluate('async ({html,password})=>OnwardExport.openHTML(html,password)', {'html':html,'password':PASSWORD})
        expect(page.get_by_role('button', name='Load existing file', exact=True)).to_be_enabled()
        # Wrong password and malformed/oversize file do not discard the download.
        bad = tmp_path / 'bad.html'
        bad.write_text('<script id="payload" type="application/json">{}</script>')
        large = tmp_path / 'large.html'
        large.write_bytes(b'x' * (10*1024*1024+1))
        for file, password in [(original,'wrong password'),(bad,PASSWORD),(large,PASSWORD)]:
            d = open_dialog(page,file,password)
            d.get_by_label('Replace my current draft', exact=True).check()
            d.get_by_role('button',name='Open and replace',exact=True).click()
            expect(d.get_by_role('alert')).not_to_be_empty()
            d.get_by_role('button',name='Cancel',exact=True).click()
            with page.expect_download() as info:
                page.get_by_role('button',name='Download onward file',exact=True).click()
            saved = tmp_path / 'preserved.html'
            info.value.save_as(saved)
            assert saved.read_text() == html
        # Explicit confirmation is mandatory; cancel and Escape preserve the artifact.
        d = open_dialog(page,original)
        expect(d.get_by_role('button',name='Open and replace',exact=True)).to_be_disabled()
        d.get_by_role('button',name='Cancel',exact=True).click()
        d = open_dialog(page,original)
        page.keyboard.press('Escape')
        expect(d).not_to_be_visible()
        expect(page.get_by_role('button',name='Download onward file',exact=True)).to_be_enabled()
        # Change the draft without changing the source file, then restore the source.
        page.get_by_role('navigation',name='Document steps').get_by_role('button',name='Edit',exact=True).click()
        page.get_by_role('button',name='Edit document title',exact=True).click()
        page.get_by_label('Document title',exact=True).fill('Temporary draft')
        page.get_by_role('button',name='Save changes',exact=True).click()
        d = open_dialog(page,original)
        d.get_by_role('button',name='Cancel',exact=True).click()
        expect(page.locator('.editor-title')).to_have_text('Temporary draft')
        d = open_dialog(page,original)
        screenshots = ROOT / 'notes/screenshots'
        screenshots.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshots/'import-desktop.png'))
        d.get_by_label('Replace my current draft',exact=True).check()
        d.get_by_role('button',name='Open and replace',exact=True).click()
        expect(d).not_to_be_visible()
        expect(page.locator('.editor-title')).to_have_text(original_data['title'])
        expect(page.get_by_role('navigation',name='Document steps').get_by_role('button',name='Download',exact=True)).to_be_disabled()
        expect(page.locator('[data-label="Password"]').first).to_have_text(secret)
        page.get_by_role('navigation',name='Document steps').get_by_role('button',name='Encrypt',exact=True).click()
        expect(page.get_by_label('Password',exact=True)).to_have_value('')
        expect(page.get_by_label('Confirm password',exact=True)).to_have_value('')
        page.get_by_role('button',name='Back to Edit',exact=True).click()
        page.get_by_role('button',name='Edit row Email',exact=True).click()
        page.get_by_label('Instruction',exact=True).fill('Updated after import\nStill private')
        page.get_by_role('button',name='Save changes',exact=True).click()
        new_html = encrypt_download(page,tmp_path/'updated.html', 'A different password 456')
        restored = page.evaluate('async ({html,password})=>OnwardExport.openHTML(html,password)', {'html':new_html,'password':'A different password 456'})
        assert restored['blocks'][0]['rows'][0]['password'] == secret
        assert restored['blocks'][0]['rows'][0]['instruction'] == 'Updated after import\nStill private'
        old_ids = {b['id'] for b in original_data['blocks']} | {r['id'] for b in original_data['blocks'] for r in b['rows']}
        new_ids = [b['id'] for b in restored['blocks']] + [r['id'] for b in restored['blocks'] for r in b['rows']]
        assert not old_ids.intersection(new_ids)
        assert len(new_ids) == len(set(new_ids))
        context.set_offline(True)
        recipient = context.new_page()
        recipient.goto((tmp_path/'updated.html').as_uri())
        recipient.locator('#password').fill('A different password 456')
        recipient.locator('#unlock').click()
        expect(recipient.locator('#document')).to_contain_text('Updated after import')
        recipient.get_by_role('button',name='Reveal password',exact=True).first.click()
        expect(recipient.get_by_label('Stored password').first).to_have_text(secret)
        assert not outbound
        assert not errors
        browser.close()


def test_import_mobile_layout(tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':390,'height':844})
        load_site(page)
        page.get_by_role('button',name='Create an onward file',exact=True).click()
        for width in [320,390]:
            page.set_viewport_size({'width':width,'height':844})
            page.get_by_role('button',name='Load existing file',exact=True).click()
            d = page.get_by_role('dialog',name='Load existing file',exact=True)
            file = d.get_by_label('Encrypted onward file',exact=True)
            file.set_input_files({'name':'a-very-long-encrypted-onward-filename-for-testing-layout.html','mimeType':'text/html','buffer':b'not a file'})
            checkbox = d.get_by_label('Replace my current draft',exact=True).bounding_box()
            assert checkbox['width'] <= 44
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert d.evaluate('(d)=>d.scrollWidth <= d.clientWidth')
            for locator in [d, file, d.get_by_label('File password',exact=True), page.locator('.editor-toolbar')]:
                box = locator.bounding_box()
                assert box['x'] >= 0 and box['x'] + box['width'] <= width
            if width == 390:
                page.screenshot(path=str(ROOT/'notes/screenshots/import-mobile.png'))
            d.get_by_role('button',name='Cancel',exact=True).click()
        browser.close()


def test_busy_and_inflight_cancel_are_transactional(tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(accept_downloads=True)
        load_site(page)
        page.get_by_role('button',name='Create an onward file',exact=True).click()
        original = tmp_path/'source.html'
        html = encrypt_download(page, original)
        d = open_dialog(page, original)
        d.get_by_label('Replace my current draft',exact=True).check()
        disabled = d.evaluate("""d => {
            d.querySelector('form').requestSubmit();
            const disabled = Array.from(document.querySelectorAll('.editor-toolbar button')).every(b=>b.disabled);
            d.close(); return disabled;
        }""")
        assert disabled
        expect(page.locator('main[aria-busy="true"]')).to_have_count(0)
        with page.expect_download() as info:
            page.get_by_role('button',name='Download onward file',exact=True).click()
        target = tmp_path/'still-original.html'
        info.value.save_as(target)
        assert target.read_text() == html
        page.get_by_role('button',name='Back to Encrypt',exact=True).click()
        # Failed/canceled import preserves existing encryption fields too.
        expect(page.get_by_label('Password',exact=True)).to_have_value(PASSWORD)
        expect(page.get_by_label('Confirm password',exact=True)).to_have_value(PASSWORD)
        busy = page.get_by_role('button',name='Encrypt and continue',exact=True).evaluate("""b=>{
            b.click(); return Array.from(document.querySelectorAll('.editor-toolbar button')).every(b=>b.disabled);
        }""")
        assert busy
        expect(page.get_by_role('button',name='Download onward file',exact=True)).to_be_enabled()
        browser.close()
