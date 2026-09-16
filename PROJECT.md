# onward

Public offline-first encrypted secret-file generator at https://onward.pat.foo.

## Scope

Document-like Edit → Encrypt → Download, optional **Load existing file**. All document handling stays in the browser. Single-password exports use real WebCrypto AES-256-GCM with PBKDF2-HMAC-SHA-256 (600,000 iterations), fresh salt/IV, and authenticated decryption. Multi-part and Seedphrase are disabled coming-soon features.

**Download the generator** saves one self-contained offline HTML editor without the current draft/passwords. **Try it out** offers a real encrypted sample with fictional data.

## Deployment

- Source: `/home/agent/projects/onward`
- URL: `https://onward.pat.foo`
- Container: `onward`
- Loopback: `127.0.0.1:3029` → container `8000`
- Canonical Compose: `/opt/dockge/stacks/proj-onward/compose.yaml`
- No site-access password, sessions, document upload endpoints, or backend vault storage.
- Old host-only `.env` is not required or injected for public serving.
- Notes, tests, configuration, and source templates/modules are not public endpoints.

## Release boundaries

The cryptographic primitives are standard browser implementations, not obfuscation. Automated tests and code review are not an independent security audit or certification. Password entropy, trusted executable code, safe devices, independent backups, and separately preserved opening passwords remain necessary. HTML files are executable; import unfamiliar vaults through a trusted generator rather than running their scripts. No perpetual compatibility, memory-erasure, or password-recovery guarantee.

Build with `python3 build.py`, test with `.venv/bin/python -m pytest -q`, and deploy only the canonical Onward compose service. README.md documents usage and threat boundaries; notes/ contains private release evidence.
