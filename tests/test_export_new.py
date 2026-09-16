"""Real Chromium/file:// tests for the standalone export (no server required)."""
import base64
import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'a long unique passphrase 42!'
DATA = {'title': 'Private title marker\nFor my family', 'blocks': [{'id': 'block-secret-id', 'title': 'Accounts marker', 'description': 'Private description marker', 'rows': [{'id': 'row-secret-id', 'item': 'Bank marker', 'username': 'private@example.test', 'password': 'ROW-secret-9385', 'instruction': 'Call my adviser marker'}]}]}


@pytest.fixture
def page(tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = browser.new_context()
        page = context.new_page()
        blank = tmp_path / 'blank.html'
        blank.write_text('<!doctype html><title>Generator test</title>')
        page.goto(blank.as_uri())
        module = ROOT / 'site/export.js'
        if module.exists():
            page.add_script_tag(path=str(module))
        yield page
        browser.close()


def create(page, data=DATA):
    assert page.evaluate('typeof window.OnwardExport') == 'object', 'export API is missing'
    return page.evaluate('async ([d,p]) => await OnwardExport.createHTML(d,p)', [data, PASSWORD])


def open_html(page, tmp_path, html):
    target = tmp_path / 'export.html'
    target.write_text(html)
    page.goto(target.as_uri())


def test_encrypted_envelope_roundtrip_and_randomness(page):
    html = create(page)
    other = create(page)
    assert html != other
    for value in [PASSWORD, *DATA['title'].splitlines(), 'block-secret-id', 'row-secret-id', 'Accounts marker', 'Private description marker', 'Bank marker', 'private@example.test', 'ROW-secret-9385', 'Call my adviser marker']:
        assert value not in html
    envelope = json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert envelope['iterations'] == 600000
    assert len(base64.b64decode(envelope['salt'])) == 16
    assert len(base64.b64decode(envelope['iv'])) == 12
    decoded = page.evaluate('''async ([e,password]) => {
        const bytes=s=>Uint8Array.from(atob(s), c=>c.charCodeAt(0));
        const base=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveKey']);
        const key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:bytes(e.salt),iterations:600000,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['decrypt']);
        return JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:bytes(e.iv)},key,bytes(e.ciphertext))));
    }''', [envelope, PASSWORD])
    assert decoded == DATA
    result = page.evaluate('async d => {try {await OnwardExport.createHTML(d,"short"); return "accepted"} catch(e) {return e.message}}', DATA)
    assert '12' in result


@pytest.mark.parametrize('newline', ['\r', '\n', '\r\n'])
def test_rejects_opening_password_line_breaks(page, newline):
    result = page.evaluate('''async ([d,p]) => {
        try { await OnwardExport.createHTML(d,p); return 'accepted'; }
        catch (error) { return error.message; }
    }''', [DATA, PASSWORD + newline + 'suffix'])
    assert 'line break' in result.lower()


def test_offline_unlock_reject_and_relock(page, tmp_path):
    html = create(page)
    requests = []
    page.on('request', lambda req: requests.append(req.url) if req.url.startswith(('http:', 'https:')) else None)
    page.context.set_offline(True)
    open_html(page, tmp_path, html)
    assert page.get_by_role('button', name='Unlock', exact=True).count() == 1
    assert DATA['title'] not in page.locator('body').inner_text()
    page.get_by_label('Export password', exact=True).fill('incorrect password')
    page.get_by_role('button', name='Unlock', exact=True).click()
    page.get_by_role('alert').filter(has_text='Unable to unlock').wait_for()
    page.get_by_label('Export password', exact=True).fill(PASSWORD)
    page.get_by_role('button', name='Unlock', exact=True).click()
    page.locator('#document h1').wait_for()
    assert page.locator('#document h1').inner_text() == DATA['title']
    assert page.locator('#document h2').inner_text() == 'Accounts marker'
    assert page.locator('#document table').inner_text().find('private@example.test') >= 0
    assert page.get_by_label('Export password', exact=True).input_value() == ''
    page.get_by_role('button', name='Lock', exact=True).click()
    assert page.locator('#document').inner_html() == ''
    assert 'ROW-secret-9385' not in page.content()
    assert requests == []
    # A changed authentication tag must fail, just like an incorrect password.
    match = re.search(r'"ciphertext":"([^"]+)"', html)
    raw = bytearray(base64.b64decode(match.group(1)))
    raw[-1] ^= 1
    tampered = html.replace(match.group(1), base64.b64encode(raw).decode())
    open_html(page, tmp_path, tampered)
    page.get_by_label('Export password', exact=True).fill(PASSWORD)
    page.get_by_role('button', name='Unlock', exact=True).click()
    page.get_by_role('alert').filter(has_text='Unable to unlock').wait_for()
    assert page.locator('#document').inner_html() == ''


@pytest.mark.parametrize('damage', [
    'invalid-json', 'null', 'array', 'missing-fields', 'iterations',
    'salt-type', 'salt-length', 'iv-length', 'ciphertext-base64',
    'ciphertext-length', 'preview-data',
])
def test_damaged_payload_disables_gate_without_page_errors(page, tmp_path, damage):
    html = create(page)
    pattern = r'(<script id="payload" type="application/json">)(.*?)(</script>)'
    envelope = json.loads(re.search(pattern, html, re.S).group(2))
    replacements = {
        'invalid-json': '{"iterations":', 'null': 'null', 'array': '[]',
        'missing-fields': '{}', 'preview-data': '{"preview":true,"data":null}',
    }
    mutations = {
        'iterations': ('iterations', 1), 'salt-type': ('salt', 123),
        'salt-length': ('salt', 'AA=='), 'iv-length': ('iv', 'AA=='),
        'ciphertext-base64': ('ciphertext', '!not-base64!'),
        'ciphertext-length': ('ciphertext', 'AA=='),
    }
    if damage in mutations:
        key, value = mutations[damage]
        envelope[key] = value
    payload = replacements.get(damage, json.dumps(envelope))
    html = re.sub(pattern, lambda m: m.group(1) + payload + m.group(3), html, flags=re.S)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    open_html(page, tmp_path, html)
    assert errors == [], f'unhandled page errors: {errors}'
    assert 'damaged or unsupported' in page.locator('#error').inner_text().lower()
    assert page.locator('#password').is_disabled()
    assert page.locator('#unlock').is_disabled()
    assert page.locator('#gate').is_visible()
    assert page.locator('#document').inner_html() == ''
    assert page.locator('#lock').is_hidden()


def test_mask_modal_theme_and_mobile_reading(page, tmp_path):
    html = create(page)
    page.emulate_media(color_scheme='dark')
    page.set_viewport_size({'width': 390, 'height': 844})
    open_html(page, tmp_path, html)
    page.get_by_label('Export password', exact=True).fill(PASSWORD)
    page.get_by_role('button', name='Unlock', exact=True).click()
    page.locator('#document h1').wait_for()
    secret = page.locator('#document input[type="password"]')
    assert secret.count() == 1, 'row password must be masked'
    assert secret.input_value() == DATA['blocks'][0]['rows'][0]['password']
    page.locator('#document').get_by_role('button', name='Reveal password').click()
    assert page.locator('#document input[type="text"]').input_value() == 'ROW-secret-9385'
    page.locator('#document').get_by_role('button', name='Hide password').click()
    page.get_by_role('button', name='View instruction').click()
    modal = page.get_by_role('dialog')
    assert modal.is_visible()
    for value in ['Bank marker', 'private@example.test', 'Call my adviser marker']:
        assert value in modal.inner_text()
    assert modal.locator('input[type="password"]').input_value() == 'ROW-secret-9385'
    modal.get_by_role('button', name='Reveal password').click()
    assert modal.locator('input[type="text"]').input_value() == 'ROW-secret-9385'
    page.keyboard.press('Escape')
    assert page.locator('#detail-content').inner_html() == ''
    page.get_by_role('button', name='View instruction').click()
    modal.get_by_role('button', name='Close').click()
    page.get_by_role('button', name='Lock', exact=True).click()
    assert page.locator('#detail-content').inner_html() == ''
    assert page.locator('#document').inner_html() == ''
    assert page.locator('html').get_attribute('data-theme') == 'dark'
    page.get_by_role('button', name='Switch to light mode').click()
    assert page.locator('html').get_attribute('data-theme') == 'light'
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('#gate h1').evaluate("e=>getComputedStyle(e).fontFamily").startswith('Georgia')


def test_preview_is_plainly_labeled_safe_and_network_blocked(page, tmp_path):
    assert page.evaluate('typeof OnwardExport.previewHTML') == 'function', 'preview API is missing'
    attack = '</script><script>window.pwned=1</script><img src="https://example.test/leak" onerror="window.pwned=2">'
    data = json.loads(json.dumps(DATA))
    data['title'] = attack + '\nSecond line <b>not bold</b>'
    data['blocks'][0]['title'] = attack
    data['blocks'][0]['description'] = attack
    for key in ['item', 'username', 'password', 'instruction']:
        data['blocks'][0]['rows'][0][key] = attack
    html = page.evaluate('d => OnwardExport.previewHTML(d)', data)
    open_html(page, tmp_path, html)
    assert page.get_by_text('Preview — not encrypted', exact=True).is_visible()
    assert page.locator('#gate').is_hidden()
    assert page.locator('#document h1').inner_text() == data['title']
    assert page.locator('#document h2').inner_text() == attack
    assert page.locator('#document .block-intro p').inner_text() == attack
    assert page.locator('#document img, #document script, #document b').count() == 0
    assert page.evaluate('window.pwned || null') is None
    page.get_by_role('button', name='View instruction').click()
    assert attack in page.get_by_role('dialog').inner_text()
    assert page.get_by_role('dialog').locator('input').input_value() == attack
    csp = page.locator('meta[http-equiv="Content-Security-Policy"]').get_attribute('content')
    for directive in ["default-src 'none'", "connect-src 'none'", "form-action 'none'", "base-uri 'none'", "object-src 'none'"]:
        assert directive in csp
    assert "'unsafe-inline'" not in csp
    assert page.locator('script[src],link[href],iframe,img').count() == 0
    blocked = page.evaluate("async () => { try {await fetch('https://example.test/leak');return false} catch (_) {return true} }")
    assert blocked
    page.evaluate("() => {const s=document.createElement('script');s.textContent='window.injected=true';document.body.append(s)}")
    assert page.evaluate('window.injected || null') is None
    assert 'trusted device' in page.locator('footer').text_content()
    assert 'not securely erase' in page.locator('footer').text_content()


def test_rejects_invalid_data_before_exporting(page):
    invalid = [None, {}, {'title': 7, 'blocks': []}, {'title': 'x', 'blocks': {}}, {'title': 'x', 'blocks': [None]}, {'title': 'x', 'blocks': [{'id': 'b', 'title': 'x', 'description': '', 'rows': [{}]}]}]
    for data in invalid:
        result = page.evaluate('async ([d,p])=>{try {await OnwardExport.createHTML(d,p);return "accepted"}catch(e){return e.message}}', [data, PASSWORD])
        assert result != 'accepted', f'invalid data accepted: {data}'
        assert 'data' in result.lower()
    for password in [None, 123456789012, '😀' * 11]:
        assert page.evaluate('async ([d,p])=>{try{await OnwardExport.createHTML(d,p);return false}catch(e){return true}}', [DATA, password])
    assert page.evaluate('d=>{try{OnwardExport.previewHTML(d);return false}catch(e){return true}}', None)


def test_block_intro_and_discreet_security_notes(page, tmp_path):
    html = page.evaluate('d=>OnwardExport.previewHTML(d)', DATA)
    open_html(page, tmp_path, html)
    intro = page.locator('.block-intro')
    assert intro.count() == 1, 'title and description need a grouped introduction'
    assert intro.locator('h2').inner_text() == 'Accounts marker'
    assert intro.locator('p').inner_text() == 'Private description marker'
    assert intro.evaluate("e=>parseFloat(getComputedStyle(e).borderRadius)") >= 12
    assert page.get_by_text('Security notes', exact=True).is_visible()
    assert page.locator('footer details').get_attribute('open') is None
    assert 'trusted device' not in page.locator('footer').inner_text()
    page.get_by_text('Security notes', exact=True).click()
    assert 'trusted device' in page.locator('footer').inner_text()
    assert 'not securely erase' in page.locator('footer').inner_text()


def test_preview_inherits_manual_parent_theme(page, tmp_path):
    page.emulate_media(color_scheme='light')
    html = page.evaluate("d=>{document.documentElement.dataset.theme='dark';return OnwardExport.previewHTML(d)}", DATA)
    encrypted = create(page)
    open_html(page, tmp_path, html)
    assert page.locator('html').get_attribute('data-theme') == 'dark'
    open_html(page, tmp_path, encrypted)
    assert page.locator('html').get_attribute('data-theme') == 'light'
