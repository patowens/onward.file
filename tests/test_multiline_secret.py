from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def test_multiline_stored_secret_reveals_without_losing_characters(tmp_path):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.goto((ROOT/'site/index.html').as_uri())
        page.add_script_tag(path=str(ROOT/'site/export.js'))
        secret='first line\r\nsecond line\nthird line'
        data={'title':'Test','blocks':[{'id':'b','title':'Block','description':'Description','rows':[{'id':'r','item':'Secret','username':'User','password':secret,'instruction':'Keep all lines'}]}]}
        html=page.evaluate('(data)=>OnwardExport.previewHTML(data)',data)
        target=tmp_path/'preview.html';target.write_text(html)
        page.goto(target.as_uri())
        page.get_by_role('button',name='Reveal password',exact=True).click()
        assert page.get_by_label('Stored password',exact=True).text_content()==secret
        page.get_by_role('button',name='Hide password',exact=True).click()
        assert secret not in page.get_by_label('Stored password',exact=True).text_content()
        browser.close()
