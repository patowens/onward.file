"""Isolated UI contract. Export is deliberately stubbed, not crypto-tested here."""
import re
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(5000)
        errors=[]
        page.on('pageerror',lambda error: errors.append(str(error)))
        styles = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>', (ROOT/'site/index.html').read_text(), re.S))
        page.set_content('<html data-theme="dark"><head><style>'+styles+'</style></head><body class="intro-mode"><section id="recipient-intro">Landing preserved</section><header class="topbar">Old header</header><div class="warning">Old warning</div><div class="layout">Old editor</div></body></html>')
        page.evaluate('''() => {window.exportCalls=[]; window.OnwardExport={previewHTML(data){window.previewData=data;return '<!doctype html><html><body>Recipient preview</body></html>';},async createHTML(data,password){window.exportCalls.push({data,password});if(window.exportFailure)throw new Error('Export failed'); if(window.exportWait)await new Promise(r=>window.finishExport=r);return '<!doctype html><html><body>Encrypted fixture only</body></html>';}};}''')
        for filename, method in [('editor.css',page.add_style_tag),('editor.js',page.add_script_tag)]:
            path=ROOT/'site'/filename
            if path.exists(): method(path=str(path))
        yield page
        browser.close()
        assert not errors, errors

def mount(page):
    assert page.evaluate('typeof window.OnwardEditor') == 'object', 'Editor mount API missing'
    page.evaluate('OnwardEditor.mount()')

def test_mount_preserves_landing_and_renders_document(page):
    mount(page)
    expect(page.locator('#recipient-intro')).to_be_hidden()
    assert page.locator('#recipient-intro').text_content() == 'Landing preserved'
    for selector in ['.topbar','.warning','.layout']:
        expect(page.locator(selector)).to_be_hidden()
    expect(page.locator('body')).to_have_class('editor-mode')
    expect(page.locator('#onward-editor h1')).to_have_text('It’s okay.\nThis file has the details\nto help you - onward.')
    expect(page.get_by_role('heading',name='Hi darling')).to_be_visible()
    expect(page.get_by_text('jamie@example.test',exact=True)).to_be_visible()
    expect(page.get_by_role('navigation',name='Document steps').get_by_role('button')).to_have_text(['Edit','Encrypt','Download'])
    page.evaluate('OnwardEditor.mount()')
    expect(page.locator('#onward-editor')).to_have_count(1)


def test_edit_document_blocks_and_rows_with_keyboard_controls(page):
    mount(page)
    page.get_by_role('button',name='Edit document title',exact=True).click()
    page.get_by_label('Document title',exact=True).fill('Dear family\n<script>no()</script>')
    page.get_by_role('button',name='Save changes').click()
    expect(page.locator('#onward-editor h1')).to_have_text('Dear family\n<script>no()</script>')
    page.get_by_role('button',name='Edit block Hi darling',exact=True).click()
    page.get_by_label('Block title',exact=True).fill('Important accounts')
    page.get_by_label('Description',exact=True).fill('First line\nSecond line')
    page.get_by_role('button',name='Save changes').click()
    page.get_by_role('button',name='Edit row Email',exact=True).click()
    for label,value in [('Item','My email'),('Username','<img src=x onerror=alert(1)>'),('Password','secret & < >'),('Instruction','Use this\nthen that')]:
        page.get_by_label(label,exact=True).fill(value)
    page.get_by_role('button',name='Save changes').click()
    expect(page.locator('.editor-row').first).to_contain_text('secret & < >')
    expect(page.locator('#onward-editor img')).to_have_count(0)
    page.get_by_role('button',name='Move row My email down',exact=True).click()
    expect(page.locator('.editor-row').nth(1)).to_contain_text('My email')
    page.get_by_role('button',name='Move row My email up',exact=True).click()
    page.get_by_role('button',name='Add row',exact=True).click()
    page.get_by_label('Item',exact=True).fill('New account')
    page.get_by_role('button',name='Save changes').click()
    expect(page.locator('.editor-row')).to_have_count(4)
    page.get_by_role('button',name='Delete row New account',exact=True).click()
    page.get_by_role('button',name='Add block',exact=True).click()
    page.get_by_label('Block title',exact=True).fill('Other details')
    page.get_by_role('button',name='Save changes').click()
    page.get_by_role('button',name='Move block Other details up',exact=True).click()
    expect(page.locator('.editor-section h2').first).to_have_text('Other details')
    page.get_by_role('button',name='Move block Other details down',exact=True).click()
    page.get_by_role('button',name='Remove block Other details',exact=True).click()
    expect(page.locator('.editor-section')).to_have_count(1)
    page.evaluate('OnwardEditor.mount()')
    expect(page.locator('#onward-editor h1')).to_contain_text('Dear family')


def test_encrypt_guard_validation_preview_download_and_invalidation(page):
    mount(page)
    nav=page.get_by_role('navigation',name='Document steps')
    expect(nav.get_by_role('button',name='Download',exact=True)).to_be_disabled()
    expect(page.get_by_role('button',name='Preview',exact=True)).to_have_count(0)
    page.get_by_role('button',name='Continue to Encrypt').click()
    expect(page.get_by_role('button',name='Multi-part — coming soon')).to_be_disabled()
    expect(page.get_by_role('button',name='Seedphrase (12–24 words) — coming soon')).to_be_disabled()
    expect(page.get_by_label('Password',exact=True)).to_have_attribute('autocomplete','new-password')
    page.get_by_label('Password',exact=True).fill('short')
    page.get_by_label('Confirm password',exact=True).fill('short')
    page.get_by_role('button',name='Encrypt and continue').click()
    expect(page.get_by_role('alert')).to_contain_text('at least 12 characters')
    page.get_by_label('Password',exact=True).fill('long enough password')
    page.get_by_role('button',name='Encrypt and continue').click()
    expect(page.get_by_role('alert')).to_contain_text('do not match')
    assert page.evaluate('exportCalls.length') == 0
    page.get_by_label('Confirm password',exact=True).fill('long enough password')
    page.get_by_role('button',name='Encrypt and continue').click()
    expect(page.get_by_role('button',name='Download onward file')).to_be_visible()
    assert page.evaluate('exportCalls[0].data.blocks[0].rows[0].item') == 'Email'
    with page.expect_download() as download:
        page.get_by_role('button',name='Download onward file').click()
    assert download.value.suggested_filename == 'onward.html'
    assert 'Encrypted fixture only' in Path(download.value.path()).read_text()
    page.get_by_role('button',name='Back to Encrypt').click()
    page.get_by_label('Password',exact=True).fill('different password')
    expect(nav.get_by_role('button',name='Download',exact=True)).to_be_disabled()
    page.get_by_role('button',name='Back to Edit').click()
    page.get_by_role('button',name='Edit document title',exact=True).click()
    page.get_by_label('Document title',exact=True).fill('Updated document')
    page.get_by_role('button',name='Save changes').click()
    expect(nav.get_by_role('button',name='Download',exact=True)).to_be_disabled()


def test_encryption_busy_failure_and_retry(page):
    mount(page)
    page.get_by_role('button',name='Continue to Encrypt').click()
    page.get_by_label('Password',exact=True).fill('long enough password')
    page.get_by_label('Confirm password',exact=True).fill('long enough password')
    page.evaluate('window.exportWait=true')
    page.get_by_role('button',name='Encrypt and continue').click()
    expect(page.get_by_role('button',name='Encrypting…')).to_be_disabled()
    expect(page.get_by_role('navigation',name='Document steps').get_by_role('button',name='Edit',exact=True)).to_be_disabled()
    page.evaluate('finishExport()')
    expect(page.get_by_role('button',name='Download onward file')).to_be_visible()
    page.get_by_role('button',name='Back to Encrypt').click()
    page.evaluate('window.exportWait=false;window.exportFailure=true')
    page.get_by_role('button',name='Encrypt and continue').click()
    expect(page.get_by_role('alert')).to_contain_text('Export failed')
    expect(page.get_by_role('navigation',name='Document steps').get_by_role('button',name='Download',exact=True)).to_be_disabled()
    page.evaluate('window.exportFailure=false')
    page.get_by_role('button',name='Encrypt and continue').click()
    expect(page.get_by_role('button',name='Download onward file')).to_be_visible()


@pytest.mark.parametrize('width',[1440,390,320])
def test_readable_responsive_document_footer_and_modal(page,width,tmp_path):
    page.set_viewport_size({'width':width,'height':900})
    mount(page)
    assert page.locator('.editor-title').evaluate("e=>getComputedStyle(e).fontFamily").startswith('Georgia')
    assert page.locator('#onward-editor').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)') >= 17
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('.editor-footer').evaluate("e=>getComputedStyle(e).position") == 'fixed'
    page.get_by_role('button',name='Add block',exact=True).scroll_into_view_if_needed()
    page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
    assert page.get_by_role('button',name='Add block',exact=True).bounding_box()['y']+44 <= page.locator('.editor-footer').bounding_box()['y']
    page.get_by_role('button',name='Edit document title',exact=True).click()
    page.get_by_label('Document title',exact=True).fill('One\nTwo\nThree')
    expect(page.get_by_role('button',name='Save changes')).to_be_in_viewport()
    page.get_by_role('button',name='Cancel').click()
    expect(page.locator('.editor-title')).to_contain_text('It’s okay.')
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(tmp_path/f'editor-{width}.png'),full_page=True)


def test_back_to_landing_requires_confirmation_and_keeps_draft_on_cancel(page):
    mount(page)
    messages=[]
    def dismiss(dialog):
        messages.append(dialog.message)
        dialog.dismiss()
    page.on('dialog',dismiss)
    page.get_by_role('button',name='Back to onward home').click()
    assert messages and 'unsaved' in messages[0].lower()
    expect(page.locator('#onward-editor')).to_be_visible()


def test_home_confirmation_clears_create_hash(page):
    mount(page)
    page.evaluate("location.hash='create'")
    page.on('dialog',lambda dialog: dialog.accept())
    page.get_by_role('button',name='Back to onward home').click()
    page.wait_for_timeout(100)
    assert '#create' not in page.url


def test_block_intro_card_matches_recipient(page):
    mount(page)
    card=page.locator('.editor-block-intro')
    expect(card).to_contain_text('Hi darling')
    assert card.evaluate('e=>parseFloat(getComputedStyle(e).borderRadius)') >= 12


def test_dark_primary_hover_preserves_contrast(page):
    mount(page)
    page.get_by_role('button',name='Continue to Encrypt').click()
    primary=page.get_by_role('button',name='Encrypt and continue')
    page.mouse.move(0,0)
    before=primary.evaluate('e=>({background:getComputedStyle(e).backgroundColor,color:getComputedStyle(e).color})')
    primary.hover()
    after=primary.evaluate('e=>({background:getComputedStyle(e).backgroundColor,color:getComputedStyle(e).color})')
    assert before == after
    assert before['background'] != before['color']


def test_footer_back_control_is_a_link_style(page):
    mount(page)
    page.get_by_role('button',name='Continue to Encrypt').click()
    expect(page.get_by_role('button',name='Back to Edit')).to_have_class('editor-link')
