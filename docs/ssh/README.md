# Office SSH materials (`docs/ssh/`)

This folder holds **reference materials only** for the office machine SSH setup. It is **not** a substitute for your real `~/.ssh` directory.

## Private keys — never in git

| Location | What belongs there |
|----------|-------------------|
| `%USERPROFILE%\.ssh\` (real home SSH dir) | **Private keys** and `config` — live **only** here |
| `docs/ssh/` (this folder) | Public key **copy** for reference, setup steps, Host alias notes |

**Never commit private keys** into this repository (or any repo). If a private key file appears under `docs/ssh/`, delete it and rotate the key.

## What this folder stores

1. **Public key copy** — `id_ed25519_office_cp_ofce.pub` (safe to share / paste into GitHub)
2. **Setup steps** — see [SETUP.md](SETUP.md)
3. **Host alias** — `github.com-office-cp` (office push identity, separate from home `github.com`)

## Related docs

- Longer office-vs-home explanation: [../SSH_OFFICE.md](../SSH_OFFICE.md)
