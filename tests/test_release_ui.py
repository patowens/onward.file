"""Public release security disclosure and generator isolation regressions."""
from playwright.sync_api import sync_playwright, expect
from test_import import load_site, ROOT


def test_encrypt_explains_real_encryption_and_limits():
    with sync_playwright() as p:
        browser=p.chromium.launch(args=['--host-resolver-rules=MAP onward.pat.foo 127.0.0.1'])
        page=browser.new_page()
        load_site(page)
        page.get_by_role('button',name='Create an onward file',exact=True).click()
        page.get_by_role('button',name='Continue to Encrypt',exact=True).click()
        disclosure=page.locator('details.editor-security')
        expect(disclosure).to_have_count(1)
        disclosure.locator('summary').click()
        for text in ['AES-256-GCM', '600,000', 'independent security audit', 'compromised device', 'long, unique password', 'backup', 'trusted source']:
            expect(disclosure).to_contain_text(text)
        for width in [1440,390]:
            page.set_viewport_size({'width':width,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(ROOT/f'notes/screenshots/release-security-{width}.png'))
        browser.close()
