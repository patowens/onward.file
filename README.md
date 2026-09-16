# onward

![Vibe-coded](https://img.shields.io/badge/vibe--coded-100%25-ff69b4)

Offline-capable encrypted secret-file generator.

## Use it

1. **Edit** — write your opening message and add/edit/reorder blocks and account rows. Editing stays in the current tab.
2. **Encrypt** — choose and confirm a long, unique opening password. Single password is available; Multi-part and Seedphrase are disabled, not implemented features.
3. **Download** — save the self-contained encrypted HTML file. Test that it unlocks, keep a backup, and share its password separately.

The floating footer provides next/back actions. Editing invalidates an earlier prepared download. Closing or refreshing the editor discards the draft; there is no autosave or cloud vault.

### Fully offline creation

**Download the generator** in the editor saves `onward-generator.html`. Open that file in a modern desktop browser to create, encrypt, download, and reopen Onward files without a server or internet connection. It packages the generator code, styling, and bundled font, **not the current draft, entered passwords, or prepared vault**. A generator can make a fresh copy of itself offline.

The landing page's **Try it out** modal downloads a genuinely encrypted sample containing fictional accounts. Its deliberately public sample password is `super-secret-only-mary-knows`; do not use that password for real information. The landing table's hide/reveal interaction is only a visual demonstration, not encryption.

### Reopen and edit a file

1. Choose **Load existing file** in the editor.
2. Select an encrypted Onward HTML file (maximum **10 MiB**) and enter its file password.
3. Save a backup of the current draft if needed, check **Replace my current draft**, and select **Open and replace**.
4. Make changes, choose and confirm the password again, encrypt, and download a new file. The original file is not overwritten.

Cancel, Escape, and failed decryption preserve the current draft and prepared download. Successful loading clears encryption-password fields and invalidates any earlier download. Import parses the encrypted payload inertly: selected HTML scripts and markup are never executed or attached to the page.

## Security model

- **Real authenticated encryption:** browser WebCrypto AES-256-GCM, with a fresh cryptographically random 16-byte salt and 12-byte IV on each export. PBKDF2-HMAC-SHA-256, 600,000 iterations, derives a 256-bit key from the opening password. GCM provides a 128-bit authentication tag. The complete title, headings, account rows, and instructions are encrypted together.
- **Local processing:** no account, login, analytics, external assets, document uploads, or vault storage API. The only localStorage value used is the theme preference. Documents are held in tab memory while editing/unlocked.
- **Password strength matters:** a file holder can attempt unlimited offline guesses. Use a password-manager-generated password or several independently random words. A length minimum alone is not a strength guarantee. There is no password reset or recovery.
- **Trust the executable:** HTML files contain executable JavaScript. Encryption authenticates the ciphertext, not the HTML application's code or the identity of its author. Only execute files from trusted sources. Use **Load existing file** in a trusted generator to read unfamiliar Onward files without running their code.
- **Endpoint limitations:** this cannot protect against a compromised generator/website, browser, extension, operating system, unlocked session, screenshots, clipboard capture, or someone who already knows the password. JavaScript cannot guarantee physical memory erasure.
- **Durability:** keep multiple backups and separately preserve the opening password and a trusted generator. Periodically test recovery and migrate while the browser/platform still works. No perpetual compatibility guarantee.
- **Assurance:** automated functional, negative-security, and interoperability tests plus code review are not an independent professional security audit or certification. Obtain an independent audit before marketing it as audited or relying on it as the only copy of irreplaceable high-value secrets.

WebCrypto PBKDF2 was retained for native offline browser portability and compatibility with existing files, rather than adding a downloaded crypto library. Argon2id is memory-hard and is generally preferred where available; PBKDF2 is not memory-hard. OWASP currently lists 600,000 iterations for PBKDF2-HMAC-SHA-256: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#pbkdf2 . This does not imply OWASP endorsement or FIPS certification of Onward.

## Development and release

`site/index.template.html`, `site/editor.js`, `site/editor.css`, and `site/export.js` assemble into a self-contained `site/index.html`:

```sh
python3 build.py
.venv/bin/python -m pytest -q
```

`notes/` contains private review/release evidence and legacy scripts, not served assets. Run current `tests/` and `test_auth.py` (public HTTP regression coverage); old screenshot scripts can target superseded UI. The backend is a bounded read-only HTTP service behind Caddy; only explicit public assets are served. It requires no site-access credentials and accepts no document submissions.

Canonical deployment, scoped to Onward only:

```sh
python3 build.py
docker compose -f /opt/dockge/stacks/proj-onward/compose.yaml up -d --build onward
```

Port `127.0.0.1:3029` proxies to container `8000`; HTTPS is terminated by host Caddy. Keep `/opt/dockge/stacks/proj-onward/compose.yaml` authoritative. Old host `.env` credentials are no longer injected or required. `.env`, notes, templates, source modules, and tests are not public endpoints.
