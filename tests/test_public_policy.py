"""Hashed CSP on the real public build, rather than permissive inline scripts."""
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
import server

ROOT=Path(__file__).resolve().parents[1]


def test_public_browser_only_executes_bundled_scripts():
    httpd=server.make_server(('127.0.0.1',0),ROOT/'site')
    thread=threading.Thread(target=httpd.serve_forever,daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page()
            response=page.goto('http://127.0.0.1:'+str(httpd.server_address[1])+'/')
            assert response.status==200
            policy=response.headers['content-security-policy']
            scripts=policy.split('script-src ',1)[1].split(';',1)[0]
            assert "'unsafe-inline'" not in scripts
            assert "'sha256-" in scripts
            assert "frame-src 'none'" in policy
            assert 'x-robots-tag' not in response.headers
            page.get_by_role('button',name='Create an onward file',exact=True).click()
            expect(page.locator('#onward-editor')).to_be_visible()
            page.evaluate('''() => {
              window.injectedScriptRan=false;
              const script=document.createElement('script');
              script.textContent='window.injectedScriptRan=true;';
              document.body.append(script);
            }''')
            assert page.evaluate('window.injectedScriptRan') is False
            expect(page.get_by_role('link',name='DOWNLOAD THE GENERATOR',exact=True)).to_be_visible()
            browser.close()
    finally:
        httpd.shutdown();httpd.server_close();thread.join()
