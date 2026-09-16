"""Release regressions using real offline Chromium and independent OpenSSL crypto.

Requires pytest, playwright (Chromium), cryptography. Loads export.js directly,
not the generated site bundle, so tests cannot accidentally cover stale source.
"""
import base64
import hashlib
import json
import re
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = '  café 🔐 e\u0301 unique phrase 42!  '
DATA = {'title': 'PRIVATE-TITLE-7821', 'blocks': [{'id': 'b', 'title': 'Accounts',
        'description': 'PRIVATE-DESCRIPTION-2549', 'rows': [{'id': 'r',
        'item': 'Bank', 'username': 'PRIVATE-USER-1548', 'password': 'PRIVATE-SECRET-9513',
        'instruction': 'PRIVATE-INSTRUCTION-3164'}]}]}
PAYLOAD = re.compile(r'(<script id="payload" type="application/json">)(.*?)(</script>)', re.S)


@pytest.fixture
def page(tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(offline=True)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        blank = tmp_path / 'blank.html'
        blank.write_text('<!doctype html><title>Offline crypto test</title>')
        page.goto(blank.as_uri())
        page.add_script_tag(path=str(ROOT / 'site/export.js'))
        yield page
        browser.close()
        assert not errors


def create(page, data=DATA, password=PASSWORD):
    return page.evaluate('([d,p]) => OnwardExport.createHTML(d,p)', [data, password])


def envelope(html):
    return json.loads(PAYLOAD.search(html)[2])


def replace_envelope(html, env):
    return PAYLOAD.sub(lambda m: m[1] + json.dumps(env).replace('<', '\\u003c') + m[3], html)


def visit(page, tmp_path, html):
    target = tmp_path / 'recipient.html'
    target.write_text(html)
    page.goto(target.as_uri())


def unlock(page, password=PASSWORD):
    page.locator('#password').fill(password)
    page.locator('#unlock').click()


def independent_envelope(plaintext, password=PASSWORD):
    # Fixed test vector inputs only; production must use fresh CSPRNG bytes.
    salt, iv = bytes(range(16)), bytes(range(12))
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000, 32)
    cipher = AESGCM(key).encrypt(iv, plaintext, None)
    return {'iterations': 600000, 'salt': base64.b64encode(salt).decode(),
            'iv': base64.b64encode(iv).decode(), 'ciphertext': base64.b64encode(cipher).decode()}


@pytest.mark.parametrize('mutation', ['version', 'extra', 'preview-false', 'salt-whitespace', 'iv-unpadded', 'duplicate'])
def test_recipient_rejects_ambiguous_envelopes(page, tmp_path, mutation):
    html = create(page)
    env = envelope(html)
    if mutation == 'version':
        env['version'] = 2
    elif mutation == 'extra':
        env['algorithm'] = 'unknown'
    elif mutation == 'preview-false':
        env['preview'] = False
    elif mutation == 'salt-whitespace':
        env['salt'] += '\n'
    elif mutation == 'iv-unpadded':
        # Salt needs padding whereas a 12-byte IV does not.
        env['salt'] = env['salt'].rstrip('=')
    html = replace_envelope(html, env)
    if mutation == 'duplicate':
        html = html.replace('</body>', '<template>' + PAYLOAD.search(html)[0] + '</template></body>')
    visit(page, tmp_path, html)
    expect(page.locator('#error')).to_contain_text('damaged or unsupported')
    expect(page.locator('#unlock')).to_be_disabled()
    expect(page.locator('#document')).to_be_empty()


@pytest.mark.parametrize('plaintext', [b'{"title":7,"blocks":[]}', b'{"title":"bad\xff","blocks":[]}'])
def test_recipient_rejects_authenticated_invalid_plaintext(page, tmp_path, plaintext):
    html = replace_envelope(create(page), independent_envelope(plaintext))
    visit(page, tmp_path, html)
    unlock(page)
    expect(page.locator('#error')).to_contain_text('Unable to unlock')
    expect(page.locator('#document')).to_be_empty()
    expect(page.locator('#gate')).to_be_visible()


def test_password_rejects_lossy_unicode_encoding(page):
    result = page.evaluate('''async d => {
      try {await OnwardExport.createHTML(d, 'long enough password' + String.fromCharCode(0xD800)); return 'accepted';}
      catch (e) {return e.message;}
    }''', DATA)
    assert 'Unicode' in result


def test_independent_decryption_randomness_and_no_plaintext(page):
    documents = [create(page) for _ in range(4)]
    envelopes = [envelope(html) for html in documents]
    for field in ['salt', 'iv', 'ciphertext']:
        assert len({e[field] for e in envelopes}) == len(envelopes)
    for html, env in zip(documents, envelopes):
        assert set(env) == {'iterations', 'salt', 'iv', 'ciphertext'}
        assert env['iterations'] == 600000
        salt, iv, cipher = [base64.b64decode(env[k], validate=True) for k in ['salt', 'iv', 'ciphertext']]
        assert len(salt) == 16 and len(iv) == 12
        key = hashlib.pbkdf2_hmac('sha256', PASSWORD.encode(), salt, 600000, 32)
        assert json.loads(AESGCM(key).decrypt(iv, cipher, None)) == DATA
        for marker in [PASSWORD, DATA['title'], DATA['blocks'][0]['description'],
                       *[v for k, v in DATA['blocks'][0]['rows'][0].items() if k in ['username','password','instruction']]]:
            assert marker not in html


def test_independent_legacy_encryption_import_and_offline_recipient(page, tmp_path):
    attack = '</script><img src="https://attacker.invalid/leak" onerror="window.pwned=1">'
    data = json.loads(json.dumps(DATA))
    data['title'] = attack
    env = independent_envelope(json.dumps(data, ensure_ascii=False).encode())
    html = replace_envelope(create(page), env)
    requests = []
    page.on('request', lambda r: requests.append(r.url) if r.url.startswith('http') else None)
    # Four fields, no version or AAD: compatibility with the original format.
    imported = page.evaluate('([h,p])=>OnwardExport.openHTML(h,p)', [html, PASSWORD])
    assert imported == data
    visit(page, tmp_path, html)
    unlock(page, PASSWORD.strip())
    expect(page.locator('#error')).to_contain_text('Unable to unlock')
    unlock(page)
    expect(page.locator('#document h1')).to_have_text(attack)
    expect(page.locator('#document img, #document script')).to_have_count(0)
    assert not page.evaluate('Boolean(window.pwned)')
    expect(page.locator('#password')).to_have_value('')
    page.locator('#lock').click()
    expect(page.locator('#document')).to_be_empty()
    expect(page.locator('#detail-content')).to_be_empty()
    unlock(page)
    expect(page.locator('#document h1')).to_have_text(attack)
    assert requests == []


@pytest.mark.parametrize('field,offset', [('salt',0), ('iv',0), ('ciphertext',0), ('ciphertext',-1)])
def test_tampering_fails_import_and_recipient(page, tmp_path, field, offset):
    html = create(page)
    env = envelope(html)
    raw = bytearray(base64.b64decode(env[field]))
    raw[offset] ^= 1
    env[field] = base64.b64encode(raw).decode()
    html = replace_envelope(html, env)
    assert page.evaluate('''async ([h,p]) => {
      try {await OnwardExport.openHTML(h,p);return false;} catch (_) {return true;}
    }''', [html, PASSWORD])
    visit(page, tmp_path, html)
    unlock(page)
    expect(page.locator('#error')).to_contain_text('Unable to unlock')
    expect(page.locator('#document')).to_be_empty()


def test_import_is_inert_even_without_recipient_csp(page):
    html = create(page)
    hostile = '<img src="https://attacker.invalid/img" onerror="window.pwned=1">' + \
        '<iframe src="https://attacker.invalid/frame"></iframe>' + \
        '<script>window.pwned=1;fetch("https://attacker.invalid/script")</script>' + PAYLOAD.search(html)[0]
    requests = []
    page.on('request', lambda r: requests.append(r.url))
    assert page.evaluate('([h,p])=>OnwardExport.openHTML(h,p)', [hostile, PASSWORD]) == DATA
    page.wait_for_timeout(100)
    assert requests == []
    assert not page.evaluate('Boolean(window.pwned)')


@pytest.mark.parametrize('password', ['😀' * 12, 'x' * 10000, PASSWORD])
def test_valid_password_is_not_normalized_or_truncated(page, password):
    html = create(page, password=password)
    env = envelope(html)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(env['salt']), 600000, 32)
    assert json.loads(AESGCM(key).decrypt(base64.b64decode(env['iv']), base64.b64decode(env['ciphertext']), None)) == DATA
