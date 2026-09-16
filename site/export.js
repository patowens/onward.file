/* Standalone export builder. No dependencies or network requests. */
(() => {
  'use strict';
  const ITERATIONS = 600000;
  const encode = bytes => {
    let binary = '';
    for (const byte of bytes) binary += String.fromCharCode(byte);
    return btoa(binary);
  };
  // The original four-field envelope is the legacy format. Do not silently
  // interpret future versions or algorithm hints as this format.
  function encryptedBytes(envelope) {
    const fields = ['iterations', 'salt', 'iv', 'ciphertext'];
    if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope) ||
        Object.keys(envelope).length !== fields.length || !fields.every(field => Object.hasOwn(envelope, field)) ||
        envelope.iterations !== 600000) throw new Error('Unsupported encrypted file.');
    const bytes = s => {
      if (typeof s !== 'string' || s.length % 4 !== 0 || /[^A-Za-z0-9+/=]/.test(s)) throw new Error('Invalid base64.');
      const binary = atob(s);
      if (btoa(binary) !== s) throw new Error('Invalid base64.');
      return Uint8Array.from(binary, c => c.charCodeAt(0));
    };
    const salt = bytes(envelope.salt), iv = bytes(envelope.iv), ciphertext = bytes(envelope.ciphertext);
    if (salt.length !== 16 || iv.length !== 12 || ciphertext.length < 16) throw new Error('Invalid encrypted payload.');
    return {salt, iv, ciphertext};
  }
  function readEnvelope(root) {
    const payloads = [], fragments = [root];
    for (let index = 0; index < fragments.length; index++) {
      const fragment = fragments[index];
      fragment.querySelectorAll('#payload').forEach(node => payloads.push(node));
      fragment.querySelectorAll('template').forEach(node => { if (node.content) fragments.push(node.content); });
    }
    if (payloads.length !== 1 || !payloads[0].matches('script[type="application/json"]')) throw new Error('Invalid payload.');
    return JSON.parse(payloads[0].textContent);
  }
  function recipient(snapshotData, readEnvelope, encryptedBytes) {
    'use strict';
    const $ = id => document.getElementById(id);
    let envelope, encrypted;
    try {
      envelope = readEnvelope(document);
      if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) throw new Error('Invalid envelope');
      if (envelope.preview === true) {
        envelope.data = snapshotData(envelope.data);
      } else {
        encrypted = encryptedBytes(envelope);
      }
    } catch (_) {
      $('error').textContent = 'This file is damaged or unsupported. Ask the sender for a new copy.';
      $('password').disabled = true;
      $('unlock').disabled = true;
      $('gate').addEventListener('submit', event => event.preventDefault());
      return;
    }
    function element(tag, text, parent) {
      const node = document.createElement(tag);
      if (text !== undefined) node.textContent = text;
      if (parent) parent.append(node);
      return node;
    }
    const system = matchMedia('(prefers-color-scheme: dark)');
    let manualTheme = envelope.preview === true && ['dark', 'light'].includes(envelope.previewTheme) ? envelope.previewTheme : null;
    function applyTheme() {
      const theme = manualTheme || (system.matches ? 'dark' : 'light');
      document.documentElement.dataset.theme = theme;
      $('theme').textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
      $('theme').setAttribute('aria-label', 'Switch to ' + (theme === 'dark' ? 'light' : 'dark') + ' mode');
    }
    $('theme').addEventListener('click', () => {
      manualTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      applyTheme();
    });
    system.addEventListener('change', applyTheme);
    applyTheme();
    function secret(value, parent) {
      // A single-line input strips CR/LF. Preserve multiline secrets as text instead.
      if (/[\r\n]/.test(value)) {
        const wrap = element('div', undefined, parent);
        wrap.className = 'secret';
        const content = element('pre', '••••••••', wrap);
        content.className = 'multiline-secret';
        content.setAttribute('aria-label', 'Stored password');
        const toggle = element('button', 'Reveal password', wrap);
        toggle.type = 'button';
        toggle.setAttribute('aria-pressed', 'false');
        let revealed = false;
        toggle.addEventListener('click', () => {
          revealed = !revealed;
          content.textContent = revealed ? value : '••••••••';
          toggle.textContent = revealed ? 'Hide password' : 'Reveal password';
          toggle.setAttribute('aria-pressed', String(revealed));
        });
        return;
      }
      const wrap = element('div', undefined, parent);
      wrap.className = 'secret';
      const input = element('input', undefined, wrap);
      input.type = 'password';
      input.readOnly = true;
      input.autocomplete = 'off';
      input.setAttribute('aria-label', 'Stored password');
      input.value = value;
      const button = element('button', 'Reveal password', wrap);
      button.type = 'button';
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => {
        const reveal = input.type === 'password';
        input.type = reveal ? 'text' : 'password';
        button.textContent = reveal ? 'Hide password' : 'Reveal password';
        button.setAttribute('aria-pressed', String(reveal));
      });
    }
    function clearDetail() { $('detail-content').replaceChildren(); }
    $('detail').addEventListener('close', clearDetail);
    $('detail').addEventListener('cancel', clearDetail);
    $('close-detail').addEventListener('click', () => { $('detail').close(); clearDetail(); });
    function showDetail(row) {
      clearDetail();
      const dl = element('dl', undefined, $('detail-content'));
      for (const [key, label] of [['item','Item'],['username','Username'],['password','Password'],['instruction','Instruction']]) {
        element('dt', label, dl);
        const dd = element('dd', undefined, dl);
        if (key === 'password') secret(row[key], dd);
        else dd.textContent = row[key];
      }
      $('detail').showModal();
    }
    function render(data) {
      const root = $('document');
      root.replaceChildren();
      element('h1', data.title, root);
      for (const block of data.blocks) {
        const section = element('section', undefined, root);
        const intro = element('div', undefined, section);
        intro.className = 'block-intro';
        element('h2', block.title, intro);
        element('p', block.description, intro);
        const scroll = element('div', undefined, section);
        scroll.className = 'table-scroll';
        scroll.tabIndex = 0;
        scroll.setAttribute('role', 'region');
        scroll.setAttribute('aria-label', 'Account table');
        const table = element('table', undefined, scroll);
        const header = element('tr', undefined, element('thead', undefined, table));
        for (const label of ['Item', 'Username', 'Password', 'Instruction']) element('th', label, header);
        const body = element('tbody', undefined, table);
        for (const row of block.rows) {
          const tr = element('tr', undefined, body);
          element('td', row.item, tr);
          element('td', row.username, tr);
          secret(row.password, element('td', undefined, tr));
          const instruction = element('td', undefined, tr);
          const summary = element('p', row.instruction, instruction);
          summary.className = 'summary';
          const view = element('button', 'View instruction', instruction);
          view.type = 'button';
          view.addEventListener('click', () => showDetail(row));
        }
      }
    }
    function lock() {
      $('detail').close();
      clearDetail();
      $('document').querySelectorAll('input').forEach(input => { input.value = ''; });
      $('document').replaceChildren();
      $('lock').hidden = true;
      $('gate').hidden = false;
      $('password').value = '';
      $('error').textContent = '';
    }
    if (envelope.preview === true) {
      render(envelope.data);
      // Preview is deliberately plaintext and is never an encrypted export.
      envelope.data = null;
      $('payload').remove();
      $('gate').hidden = true;
    }
    $('lock').addEventListener('click', lock);
    $('gate').addEventListener('submit', async event => {
      event.preventDefault();
      const button = $('unlock');
      if (button.disabled) return;
      button.disabled = true;
      $('error').textContent = '';
      let plaintext;
      try {
        const password = $('password').value;
        $('password').value = '';
        const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
        if (envelope.iterations !== 600000) throw new Error('Unsupported parameters');
        const key = await crypto.subtle.deriveKey({name:'PBKDF2', salt:encrypted.salt, iterations:600000, hash:'SHA-256'}, base, {name:'AES-GCM', length:256}, false, ['decrypt']);
        plaintext = new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM', iv:encrypted.iv}, key, encrypted.ciphertext));
        render(snapshotData(JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(plaintext))));
        $('gate').hidden = true;
        $('lock').hidden = false;
      } catch (_) {
        lock();
        $('error').textContent = 'Unable to unlock. Check the password; the file may also be damaged or changed.';
      } finally {
        if (plaintext) plaintext.fill(0);
        button.disabled = false;
      }
    });
  }
  const styles = `
.multiline-secret{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;margin:0 0 6px}
:root{color-scheme:light;--bg:#fff;--ink:#252521;--muted:#696960;--line:#d2cfca;--shade:#f4f4f3;--odd:#e9e8e5;font:15px/1.65 Arial,Helvetica,sans-serif;background:var(--bg);color:var(--ink)}
:root[data-theme="dark"]{color-scheme:dark;--bg:#191b18;--ink:#eeeee5;--muted:#adb0a3;--line:#42463b;--shade:#252822;--odd:#30342b}
*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0;padding:28px 24px 64px}header,main,footer,#gate{width:min(960px,100%);margin:auto}header{display:flex;gap:16px;align-items:center;justify-content:space-between;margin-bottom:64px}.actions{display:flex;gap:8px;flex-wrap:wrap}.brand{font:28px Georgia,serif}h1,h2,h3{font-family:Georgia,'Times New Roman',serif;font-weight:400;line-height:1.3}h1{font-size:clamp(32px,5vw,56px);letter-spacing:-1px;white-space:pre-wrap;margin:0 0 48px;overflow-wrap:anywhere}h2{font-size:28px;margin:0 0 12px}h3{font-size:25px;margin:0}p,dd{white-space:pre-wrap;overflow-wrap:anywhere}section{margin-bottom:48px}.block-intro{padding:26px 28px;background:var(--shade);border-radius:16px;margin-bottom:20px}.block-intro p{color:var(--muted);margin:0}.preview-label{font-weight:700;text-align:center;border:1px solid var(--line);border-radius:12px;padding:12px;background:var(--odd)}details{margin-top:16px}summary{cursor:pointer;min-height:44px;padding:10px 0}button,input{font:inherit;color:inherit}button{min-height:44px;border:1px solid var(--line);border-radius:12px;background:var(--bg);padding:9px 16px;cursor:pointer}button:hover{background:var(--odd)}button:disabled{opacity:.55;cursor:wait}:focus-visible{outline:2px solid var(--ink);outline-offset:3px}input{min-height:44px;border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--shade);max-width:100%}label{display:block;margin-bottom:8px}#gate{max-width:580px;padding:28px 0 64px}#gate h1{margin-bottom:18px}#gate input{width:100%;margin:12px 0}#error{color:var(--ink)}.table-scroll{overflow-x:auto;border-radius:12px}table{width:100%;min-width:680px;table-layout:fixed;border-spacing:0;text-align:left}th{font-weight:400;font-size:12px;color:var(--muted);padding:14px 16px}td{padding:20px 16px;background:var(--shade);border-bottom:1px solid var(--line);overflow-wrap:anywhere;vertical-align:top}tbody tr:nth-child(odd)>td{background:var(--odd)}tbody tr:first-child td:first-child{border-top-left-radius:12px}tbody tr:first-child td:last-child{border-top-right-radius:12px}tbody tr:last-child td:first-child{border-bottom-left-radius:12px}tbody tr:last-child td:last-child{border-bottom-right-radius:12px}.secret input{width:100%;min-width:0;background:transparent;border:0;padding:0;font-family:monospace}.secret button,td button{font-size:12px;padding:8px}.summary{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:0 0 8px}dialog{width:min(600px,calc(100% - 32px));max-height:calc(100dvh - 32px);overflow:auto;padding:28px;border:1px solid var(--line);border-radius:16px;background:var(--bg);color:var(--ink)}dialog::backdrop{background:#0008}.detail-top{display:flex;justify-content:space-between;align-items:center;gap:16px}dt{font-size:12px;color:var(--muted);margin-top:22px}dd{margin:6px 0}body:has(dialog[open]){overflow:hidden}footer{margin-top:56px;font-size:12px;color:var(--muted)}@media(max-width:600px){body{padding:20px 16px 40px}header{margin-bottom:40px;align-items:flex-start}button{padding:9px 12px}h1{margin-bottom:32px}dialog{padding:20px}}
`;
  function documentHTML(payload) {
    const nonce = encode(crypto.getRandomValues(new Uint8Array(18)));
    const csp = "default-src 'none'; connect-src 'none'; img-src 'none'; font-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; worker-src 'none'; base-uri 'none'; form-action 'none'; script-src 'nonce-" + nonce + "'; script-src-attr 'none'; style-src 'nonce-" + nonce + "'; style-src-attr 'none'";
    const safePayload = JSON.stringify(payload).replace(/</g, '\\u003c').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="' + csp + '"><meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Onward</title><style nonce="' + nonce + '">' + styles + '</style></head>' +
      '<body>' + (payload.preview ? '<p role="status" class="preview-label">Preview — not encrypted</p>' : '') + '<header><span class="brand">onward</span><div class="actions"><button id="theme" type="button">Dark mode</button><button id="lock" type="button" hidden>Lock</button></div></header><form id="gate"><h1>A little peace of mind.</h1><p>This file opens locally. Enter its password to read what was left for you.</p><label for="password">Export password</label><input id="password" type="password" autocomplete="off" required><button id="unlock">Unlock</button><p id="error" role="alert"></p></form><main id="document"></main><dialog id="detail" aria-labelledby="detail-title"><div class="detail-top"><h3 id="detail-title">Row details</h3><button id="close-detail" type="button">Close</button></div><div id="detail-content"></div></dialog>' +
      '<footer><p>No password recovery. Keep a backup and share the password separately.</p><details><summary>Security notes</summary><p>Use a trusted device and an authentic copy of this file. A modified file, malicious browser extension, or compromised device can capture your password or unlocked information. Anyone with the encrypted file can try passwords offline; choose a long, unique passphrase and share it separately. There is no password recovery. Lock removes the displayed information but does not securely erase browser memory, screenshots, or copies. Preview contains plaintext and must not be shared as an encrypted export.</p></details></footer>' +
      '<script id="payload" type="application/json">' + safePayload + '<' + '/script><script nonce="' + nonce + '">document.addEventListener("DOMContentLoaded",()=>(' + recipient.toString() + ')(' + snapshotData.toString() + ',' + readEnvelope.toString() + ',' + encryptedBytes.toString() + '));<' + '/script></body></html>';
  }
  function snapshotData(data) {
    function object(value) {
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError('Invalid export data: expected an object.');
    }
    function text(value) {
      if (typeof value !== 'string') throw new TypeError('Invalid export data: fields must be strings.');
      return value;
    }
    function list(value) {
      if (!Array.isArray(value)) throw new TypeError('Invalid export data: expected an array.');
      return value;
    }
    object(data);
    // Copy exactly the public schema, without invoking caller-provided toJSON.
    return {title:text(data.title), blocks:list(data.blocks).map(block => {
      object(block);
      return {id:text(block.id), title:text(block.title), description:text(block.description), rows:list(block.rows).map(row => {
        object(row);
        return {id:text(row.id), item:text(row.item), username:text(row.username), password:text(row.password), instruction:text(row.instruction)};
      })};
    })};
  }
  async function createHTML(data, password) {
    if (typeof password === 'string' && /[\r\n]/.test(password)) {
      throw new Error('The opening password must not contain line breaks.');
    }
    if (typeof password !== 'string' || Array.from(password).length < 12) {
      throw new Error('Use a password of at least 12 characters.');
    }
    // TextEncoder replaces lone UTF-16 surrogates with U+FFFD. Reject those
    // on creation instead of silently deriving a key from a different password.
    if (/[\uD800-\uDFFF]/u.test(password)) throw new Error('The opening password must contain valid Unicode.');
    data = snapshotData(data);
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey({name:'PBKDF2', salt, iterations:ITERATIONS, hash:'SHA-256'}, base, {name:'AES-GCM', length:256}, false, ['encrypt']);
    const plaintext = new TextEncoder().encode(JSON.stringify(data));
    try {
      const ciphertext = await crypto.subtle.encrypt({name:'AES-GCM', iv}, key, plaintext);
      return documentHTML({iterations:ITERATIONS, salt:encode(salt), iv:encode(iv), ciphertext:encode(new Uint8Array(ciphertext))});
    } finally { plaintext.fill(0); }
  }
  function previewHTML(data) {
    const theme = document.documentElement.dataset.theme;
    return documentHTML({preview:true, previewTheme:['dark','light'].includes(theme) ? theme : null, data:snapshotData(data)});
  }
  async function openHTML(html, password) {
    if (typeof html !== 'string' || new Blob([html]).size > 10 * 1024 * 1024) throw new Error('File exceeds the 10 MiB limit.');
    if (typeof password !== 'string') throw new Error('Enter the file password.');
    // A detached template is inert, including images/frames. Never use DOMParser,
    // attach its content, or execute any imported scripts (including the recipient).
    const template = document.createElement('template');
    template.innerHTML = html;
    const envelope = readEnvelope(template.content);
    template.content.replaceChildren();
    const {salt, iv, ciphertext} = encryptedBytes(envelope);
    const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey({name:'PBKDF2', salt, iterations:ITERATIONS, hash:'SHA-256'}, base, {name:'AES-GCM', length:256}, false, ['decrypt']);
    const plaintext = new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM', iv}, key, ciphertext));
    try { return snapshotData(JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(plaintext))); }
    finally { plaintext.fill(0); }
  }
  window.OnwardExport = {createHTML, previewHTML, openHTML};
})();
