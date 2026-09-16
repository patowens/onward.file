"""Assemble a self-contained Onward page from the preserved landing and editor modules."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent

def build():
    page=(ROOT/'site/index.template.html').read_text()
    license_text=(ROOT/'LICENSE').read_text()
    font_license=(ROOT/'licenses/SourceSerif4-OFL.txt').read_text()
    notices=(ROOT/'THIRD_PARTY_NOTICES.md').read_text()
    page=page.replace('/* DISTRIBUTION_LICENSES */', license_text+'\n'+notices+'\n'+font_license)
    for token,file in [('/* EDITOR_CSS */','editor.css'),('/* EXPORT_JS */','export.js'),('/* EDITOR_JS */','editor.js')]:
        source=(ROOT/'site'/file).read_text()
        if file.endswith('.js'):
            source=re.sub(r'</script',r'<\\/script',source,flags=re.I)
        assert page.count(token)==1,token
        page=page.replace(token,source)
    (ROOT/'site/index.html').write_text(page)
    print('Built self-contained site/index.html')

if __name__=='__main__':
    build()
