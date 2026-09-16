# onward

Offline-first encrypted secret-file generator.

## Scope

Document-like Edit → Encrypt → Download, with **Load existing file** for reopening encrypted documents. All document handling stays in the browser. Single-password exports use WebCrypto AES-256-GCM with PBKDF2-HMAC-SHA-256 (600,000 iterations), fresh salt/IV, and authenticated decryption. Multi-part and Seedphrase are disabled coming-soon features.

**Download the generator** saves one self-contained offline HTML editor without the current draft/passwords. **Try it out** offers a genuinely encrypted sample containing fictional data.

## Architecture

- Source modules and template: `site/`
- Self-contained output: `site/index.html`, assembled by `build.py`
- Optional read-only web server: `server.py`; only explicit built-page routes are served
- Portable local container configuration: `docker-compose.yml`
- No site-access password, sessions, document upload endpoints, or backend vault storage
- Configuration, notes, tests and source modules are not public HTTP endpoints

See README.md for local setup, testing, and generic HTTPS hosting guidance. Production-specific infrastructure configuration belongs outside this repository.

## Release boundaries

Automated tests and code review are not an independent security audit or certification. Password entropy, trusted executable code, safe devices, independent backups, and separately preserved opening passwords remain necessary. HTML files are executable; import unfamiliar vaults through a trusted generator rather than running their scripts. No perpetual compatibility, memory-erasure, or password-recovery guarantee.

Project code: MIT. Bundled Source Serif 4 Light font: SIL OFL 1.1. See LICENSE and THIRD_PARTY_NOTICES.md.
