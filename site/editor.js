(() => {
  'use strict';
  if (window.OnwardEditor) return;
  let root;
  let counter = 0;
  const id = () => `onward-${++counter}`;
  const data = {title: 'It’s okay.\nThis file has the details\nto help you - onward.', blocks: [{id: id(), title: 'Hi darling', description: 'Here are the links and details needed to access banking, email and more, should you need to.', rows: [
    {id:id(), item:'Email', username:'jamie@example.test', password:'example-only-123', instruction:'Start here for household accounts and useful contacts. Check the Household folder for bills and the Contacts list for people who can help.'},
    {id:id(), item:'Banking', username:'jamie.demo', password:'example-bank-456', instruction:'The household bills are paid from this account. The Statements folder on the home PC has the latest records. Contact the bank through its official website for help with access.'},
    {id:id(), item:'Home PC', username:'Jamie', password:'example-pc-789', instruction:'Choose the Jamie profile on the sign-in screen. Important documents are in the Household folder on the desktop. The backup drive is in the top desk drawer.'}
  ]}]};
  const el = (tag, text, cls) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node; };
  const button = (text, fn, cls) => {const node = el('button', text, cls); node.type = 'button'; if(fn)node.addEventListener('click', fn); return node;};
  const namedButton = (text, label, fn) => {const b=button(text,fn,'editor-link');b.setAttribute('aria-label',label);return b;};
  let step=0, password='', confirmation='', artifact=null, busy=false, error='';
  const snapshot=()=>JSON.parse(JSON.stringify(data));
  function invalidate() {artifact=null; const download=root.querySelector('[data-step="2"]');if(download)download.disabled=true;}
  function changed() {invalidate();render();}
  function go(next) {if(busy||next===2&&!artifact)return;step=next;error='';render();root.querySelector('main').focus();window.scrollTo(0,0);}
  async function encrypt() {
    if(busy)return;
    if(password.length<12){error='Use at least 12 characters for your password.';render();return;}
    if(password!==confirmation){error='Passwords do not match.';render();return;}
    invalidate();busy=true;error='';render();
    try {const html=await window.OnwardExport.createHTML(snapshot(),password);if(typeof html!=='string'||!html.trim())throw new Error('Encryption did not return an HTML document.');artifact=html;step=2;}
    catch(e){error=e.message||'Could not encrypt your file. Please try again.';}
    finally {busy=false;render();root.querySelector('main').focus();}
  }
  function download() {if(!artifact||busy)return;const url=URL.createObjectURL(new Blob([artifact],{type:'text/html;charset=utf-8'}));const a=el('a');a.href=url;a.download='onward.html';root.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function downloadGenerator() {
    // Package only static styles and source modules, never the rendered editor,
    // draft, imported document, password fields, or encrypted artifact.
    const head = document.head.cloneNode(true);
    head.querySelectorAll('meta[http-equiv="Content-Security-Policy"]').forEach(node=>node.remove());
    const policy = el('meta');
    policy.httpEquiv = 'Content-Security-Policy';
    policy.content = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; font-src data:; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'";
    head.prepend(policy);
    head.querySelector('title').textContent = 'onward — offline generator';
    const boot = el('script', 'window.OnwardEditor.mount();');
    const html = '<!doctype html><html lang="en">' + head.outerHTML + '<body>' +
      document.querySelector('#theme-toggle').outerHTML +
      document.querySelector('#export-code').outerHTML +
      document.querySelector('#editor-code').outerHTML + boot.outerHTML + '</body></html>';
    const url = URL.createObjectURL(new Blob([html], {type:'text/html;charset=utf-8'}));
    const link = el('a');link.href=url;link.download='onward-generator.html';document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  }
  function renderEncrypt(main) {
    main.append(el('p','PROTECT YOUR DOCUMENT','editor-eyebrow'),el('h1','Only for the right person.','editor-title'),el('p','Choose how your onward file will be locked.','editor-description'));
    const choices=el('div',undefined,'editor-methods');const single=button('Single password');single.setAttribute('aria-pressed','true');choices.append(single);['Multi-part — coming soon','Seedphrase (12–24 words) — coming soon'].forEach(text=>{const b=button(text);b.disabled=true;choices.append(b);});main.append(choices);
    const panel=el('section',undefined,'editor-password-panel');panel.append(el('h2','Set an opening password'),el('p','Use at least 12 characters. A long, unique phrase is a good choice.'));
    [['Password',password,false],['Confirm password',confirmation,true]].forEach(([label,value,confirm])=>{const wrap=el('label',label),input=el('input');input.type='password';input.autocomplete='new-password';input.id=id();input.value=value;input.minLength=12;input.required=true;input.disabled=busy;wrap.htmlFor=input.id;input.addEventListener('input',()=>{if(confirm)confirmation=input.value;else password=input.value;invalidate();});wrap.append(input);panel.append(wrap);});
    panel.append(el('p','There is no password recovery. If the password is lost, this file cannot be opened. Share the password separately from the file.','editor-notice'));main.append(panel);
    const security=el('details',undefined,'editor-security');security.append(el('summary','How your file is protected'));
    for(const text of [
      'Your complete document is encrypted in this browser using AES-256-GCM, with a fresh random salt and IV for each file. PBKDF2-HMAC-SHA-256 derives the key from your password using 600,000 iterations. Your document and password are not uploaded.',
      'Use a long, unique password, ideally several randomly chosen words. Someone with the file can try password guesses offline; there is no server-side attempt limit or password recovery.',
      'Download a backup and test that it unlocks before relying on it. Keep the password separately. Anyone who knows the password and has the file can read it.',
      'Only open HTML files from a trusted source: they contain executable code. To load an unfamiliar onward file, use Load existing file in a trusted generator instead. Encryption cannot protect an unlocked file or a compromised device, browser extension, or generator.',
      'This release has automated security and compatibility tests, not an independent security audit. Future browser compatibility is not guaranteed. Multi-part and seedphrase protection are not available.'
    ])security.append(el('p',text));main.append(security);
  }
  function footer() {
    const f=el('footer',undefined,'editor-footer');f.append(el('span',`STEP ${step+1} OF 3 · ${['Edit','Encrypt','Download'][step]}`,'editor-eyebrow'));const actions=el('div',undefined,'editor-actions');
    if(step>0){const back=button(step===1?'Back to Edit':'Back to Encrypt',()=>go(step-1),'editor-link');back.disabled=busy;actions.append(back);}
    const next=button(step===0?'Continue to Encrypt':step===1?(busy?'Encrypting…':'Encrypt and continue'):'Download onward file',step===0?()=>go(1):step===1?encrypt:download,'editor-primary');next.disabled=busy;actions.append(next);f.append(actions);root.append(f);
  }
  function dialog(title) {
    const d=el('dialog',undefined,'editor-dialog'); const heading=el('h2',title);heading.id=id();d.setAttribute('aria-labelledby',heading.id);d.append(heading);root.append(d);
    d.addEventListener('close',()=>d.remove());return d;
  }
  function openFile() {
    if (busy) return;
    const d = dialog('Load existing file'), form = el('form');
    d.append(el('p', 'Choose an encrypted onward HTML file (up to 10 MiB). It is decrypted only in this tab. Opening it replaces your current draft; download a backup first.'));
    const field = (label, type) => {
      const wrap = el('label', label), input = el('input');
      input.type = type; input.id = id(); wrap.htmlFor = input.id;
      wrap.append(input); form.append(wrap); return input;
    };
    const file = field('Encrypted onward file', 'file');
    file.accept = '.html,.htm,text/html'; file.required = true;
    const filePassword = field('File password', 'password');
    filePassword.autocomplete = 'off'; filePassword.required = true;
    const replace = field('Replace my current draft', 'checkbox');
    replace.required = true;
    const alert = el('p', '', 'editor-error'); alert.setAttribute('role', 'alert'); alert.hidden = true;
    const submit = button('Open and replace'); submit.type = 'submit'; submit.disabled = true;
    replace.addEventListener('change', () => { submit.disabled = !replace.checked || busy; });
    const actions = el('div', undefined, 'editor-actions');
    actions.append(button('Cancel', () => d.close()), submit); form.append(alert, actions);
    d.addEventListener('close', () => { filePassword.value = ''; file.value = ''; });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy || !replace.checked || !file.files.length) return;
      const selected = file.files[0];
      if (selected.size > 10 * 1024 * 1024) {
        filePassword.value = ''; alert.hidden = false; alert.textContent = 'File exceeds the 10 MiB limit.'; return;
      }
      const openingPassword = filePassword.value; filePassword.value = '';
      busy = true; alert.hidden = true; submit.disabled = true;
      file.disabled = filePassword.disabled = replace.disabled = true;
      const controls = Array.from(root.querySelectorAll('button, input, textarea')).filter(node => !d.contains(node)).map(node => [node, node.disabled]);
      controls.forEach(([node]) => { node.disabled = true; });
      root.querySelector('main').setAttribute('aria-busy', 'true');
      let opened = false;
      try {
        const imported = await window.OnwardExport.openHTML(await selected.text(), openingPassword);
        // Closing the dialog during decryption is cancellation, never a late commit.
        if (!d.open) return;
        const blocks = imported.blocks.map(block => ({...block, id:id(), rows:block.rows.map(row => ({...row, id:id()}))}));
        data.title = imported.title; data.blocks = blocks;
        invalidate(); password = ''; confirmation = ''; error = ''; step = 0;
        opened = true; d.close();
      } catch (_) {
        if (d.open) { alert.hidden = false; alert.textContent = 'Unable to open. Check the file password. The file may be damaged, a plaintext preview, or unsupported.'; }
      } finally {
        busy = false;
        if (opened) { render(); root.querySelector('main').focus(); window.scrollTo(0, 0); }
        else {
          controls.forEach(([node, disabled]) => { node.disabled = disabled; });
          root.querySelector('main').setAttribute('aria-busy', 'false');
          file.disabled = filePassword.disabled = replace.disabled = false; submit.disabled = !replace.checked;
        }
      }
    });
    d.append(form); d.showModal();
  }
  function editFields(title, object, fields, save) {
    const d=dialog(title), form=el('form'); const inputs={};
    fields.forEach(([key,label])=>{const wrap=el('label',label);const input=el('textarea');input.id=id();wrap.htmlFor=input.id;input.value=object[key]||'';input.rows=key==='description'||key==='instruction'||key==='title'?3:1;inputs[key]=input;wrap.append(input);form.append(wrap);});
    const actions=el('div',undefined,'editor-actions');const submit=button('Save changes');submit.type='submit';actions.append(button('Cancel',()=>d.close()),submit);form.append(actions);
    form.addEventListener('submit',event=>{event.preventDefault();const values={};fields.forEach(([key])=>values[key]=inputs[key].value);save(values);d.close();changed();});d.append(form);d.showModal();
  }
  const blockFields=[['title','Block title'],['description','Description']];
  const rowFields=[['item','Item'],['username','Username'],['password','Password'],['instruction','Instruction']];
  function reorderControls(list,index,label) {
    const tools=el('div',undefined,'editor-actions');
    [-1,1].forEach(delta=>{const b=namedButton(delta<0?'↑':'↓',`Move ${label} ${delta<0?'up':'down'}`,()=>{const item=list.splice(index,1)[0];list.splice(index+delta,0,item);changed();});b.disabled=index+delta<0||index+delta>=list.length;tools.append(b);});return tools;
  }
  function render() {
    root.replaceChildren();
    const sidebar = el('aside', undefined, 'editor-sidebar');
    const home=namedButton('onward.','Back to onward home',()=>{if(window.confirm('Leave this editor? Your unsaved document and password will be lost.')){window.history.replaceState(null,'',window.location.href.split('#')[0]);window.location.reload();}});home.className='editor-brand';home.disabled=busy;sidebar.append(home);
    const nav = el('nav'); nav.setAttribute('aria-label','Document steps');
    ['Edit','Encrypt','Download'].forEach((label,index) => {const b=button(label,()=>go(index));b.dataset.step=index;b.disabled=busy||index===2&&!artifact;if(index===step)b.setAttribute('aria-current','step');nav.append(b);});
    sidebar.append(nav); root.append(sidebar);
    const main = el('main', undefined, 'editor-main');main.tabIndex=-1;main.setAttribute('aria-busy',String(busy));
    const toolbar=el('div',undefined,'editor-toolbar');const openButton=button('Load existing file',openFile);openButton.disabled=busy;const toolbarActions=el('div',undefined,'editor-actions');toolbarActions.append(openButton);
    const intro=el('span',undefined,'editor-eyebrow');const generatorLink=el('a','DOWNLOAD THE GENERATOR','generator-download');generatorLink.href='#';generatorLink.addEventListener('click',event=>{event.preventDefault();downloadGenerator();});intro.append('MAKE AN ONWARD FILE HERE. OR ',generatorLink,' FOR 100% OFFLINE CREATION');toolbar.append(intro,toolbarActions);main.append(toolbar);
    if(step===1)renderEncrypt(main);
    if(step===2)main.append(el('p','READY TO KEEP','editor-eyebrow'),el('h1','A little peace of mind.','editor-title'),el('p','Your encrypted onward file is ready. Download it and keep a copy somewhere safe.','editor-description'),el('p','The HTML file opens in a browser, even offline. Give it to someone you trust, and share the password separately.','editor-notice'));
    if(error){const alert=el('p',error,'editor-error');alert.setAttribute('role','alert');main.append(alert);}
    if(step===0)renderEdit(main);
    root.append(main);footer();
  }
  function renderEdit(main) {
    const titleline=el('div',undefined,'editor-titleline');titleline.append(el('h1',data.title,'editor-title'),namedButton('Edit','Edit document title',()=>editFields('Edit document title',data,[['title','Document title']],values=>Object.assign(data,values))));
    main.append(el('p','YOUR DOCUMENT / EDIT','editor-eyebrow'),titleline);
    data.blocks.forEach((block,index) => {
      const section = el('section', undefined, 'editor-section');
      const heading=el('div',undefined,'editor-heading');heading.append(el('h2',block.title),namedButton('Edit',`Edit block ${block.title}`,()=>editFields('Edit block',block,blockFields,values=>Object.assign(block,values))));
      const tools=reorderControls(data.blocks,index,`block ${block.title}`);tools.append(namedButton('Remove block',`Remove block ${block.title}`,()=>{data.blocks.splice(index,1);changed();}));
      const intro=el('div',undefined,'editor-block-intro');intro.append(heading,el('p',block.description,'editor-description'));section.append(intro);
      const table = el('div',undefined,'editor-table');
      const labels=el('div',undefined,'editor-table-labels');rowFields.forEach(([,label])=>labels.append(el('span',label)));labels.append(el('span','Actions'));table.append(labels);
      block.rows.forEach((row,rowIndex) => {
        const r=el('div',undefined,'editor-row');rowFields.forEach(([key,label])=>{const cell=el('div',row[key]);cell.dataset.label=label;r.append(cell);});
        const actions=reorderControls(block.rows,rowIndex,`row ${row.item}`);actions.prepend(namedButton('Edit',`Edit row ${row.item}`,()=>editFields('Edit row',row,rowFields,values=>Object.assign(row,values))));actions.append(namedButton('Delete',`Delete row ${row.item}`,()=>{block.rows.splice(rowIndex,1);changed();}));r.append(actions);table.append(r);
      });
      section.append(table,button('Add row',()=>editFields('Add row',{},rowFields,values=>block.rows.push({id:id(),...values}))),tools);main.append(section);
    });
    main.append(button('Add block',()=>editFields('Add block',{},blockFields,values=>data.blocks.push({id:id(),...values,rows:[]}))));root.append(main);
  }
  function mount() {
    document.body.classList.remove('intro-mode'); document.body.classList.add('editor-mode');
    document.querySelectorAll('#recipient-intro,body > .topbar,body > .warning,body > .layout').forEach(node => {node.hidden=true;node.style.display='none';});
    if(root)return;
    root=el('div');root.id='onward-editor';document.body.append(root);render();
  }
  window.OnwardEditor=Object.freeze({mount});
})();
