# Security and live credentials

V0.12 prepares development/test access only. **PRODUCTION UNCHANGED**.
No marketplace transaction, production deployment, auth activation or network change.

## Compromised GitHub token

A fine-grained GitHub PAT was disclosed in conversation. Treat it as compromised,
even if no Git commit contains it. Do not reuse it or paste a replacement in chat.
Revoke that token in GitHub Settings > Developer settings > Personal access tokens >
Fine-grained tokens. [Official procedure](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

Revocation is **HUMAN_ACTION_REQUIRED**, not confirmed. No authenticated revocation
interface was available in this run. The existing conversation journal is evidence,
not a credential store; no journal deletion or Git history rewrite was performed.
The dated [audit report](LIVE_CREDENTIALS_REPORT_2026-09-20.md) records the scope and limits.

## Interactive market configuration

From the repository, with Docker available:

```bash
docker build -t cs2-v012-validation-api -f apps/api/Dockerfile .
./scripts/configure-market-credentials.py
./scripts/configure-market-credentials.py --status
```

The image already exists on the development server after V0.12 validation. It is
separate from all production images. The helper runs without network, as the invoking
UID/GID, with read-only container root, no capabilities and no-new-privileges.
Only `~/.config/cs2-arbitrage-hub` is mounted writable.

- Storage: `~/.config/cs2-arbitrage-hub/markets.env`, user-owned, mode `0600`;
  containing directory `0700`, outside Git, no symlink or hard-linked secret file.
- Input: `getpass`, real terminal mandatory; empty input keeps the existing value.
  No value in arguments, shell exports, stdout, errors or browser.
- Keys: `CSFLOAT_API_KEY`, `DMARKET_PUBLIC_KEY`, `DMARKET_SECRET_KEY` only.
  DMarket pair checked with PyNaCl; GitHub token formats refused.
- Existing unrelated dotenv bindings preserved without interpolation. Invalid or
  duplicate bindings refused. Concurrent writers serialized; temp file, fsync,
  atomic replace and directory fsync. No production env file is touched.
- Before a change, the old file is backed up in that private directory, mode `0600`.
  At most three dated backups are retained. They remain sensitive; after revocation,
  an administrator should retire obsolete copies according to their backup policy.
- No file is created when every input is empty and nothing was configured.
  `--status` prints only CONFIGURED/NOT_CONFIGURED, not partial keys.

Never run a real credential entry under a shell/session recorder. Local root,
the owning account and users able to control Docker remain trusted principals.

## Explicit read-only smoke

After interactive entry, use the same file, mounted read-only. No key is duplicated
into container environment variables or command arguments:

```bash
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$HOME/.config/cs2-arbitrage-hub,dst=/credentials,readonly" \
  cs2-v012-validation-api python -m app.markets.smoke \
  --credentials-file /credentials/markets.env \
  --platform csfloat --query 'AK-47 | Redline (Field-Tested)' --live
```

Use `--platform dmarket` for one signed offer request. Add `--enrich` explicitly
to read targets, sales and fees when a matching offer exists. Authenticated smokes
request five listings at most, one page, one attempt per endpoint. No DB access,
buy/sell/trade or implicit `.env` loading. Code `0` means successful parsing;
`2` covers missing config, partial data or failure. An empty valid page does not
validate all fields or pagination. Presence counters describe normalized optional
fields, not a complete schema-drift audit. Genuine live schema comparison still
requires an authorized account and representative responses.

HTTP diagnostics retain only status, host/path without query, duration, a bounded
content-type enum, numeric quota fields/Retry-After and Cloudflare booleans.
No upstream body, cookie, Authorization, request signature, account profile or
private error text is retained. The last 16 request records are bounded in memory.

## Skinport and health

`SKINPORT_REALTIME_ENABLED=false` stays the default. No extra credential is invented.
An observed 401/403 renders BLOCKED, independently of REST and application readiness.
An administrator may record the date of an actual 403 in the test-only setting
`SKINPORT_REALTIME_BLOCKED_AT`. This is historical evidence, not a fresh check.
It cannot coexist with an enabled stream; clear it only after resolving access.
Unset means UNKNOWN/DISABLED, not an inferred provider refusal. The setting does
not make network requests. API and DB alone determine readiness.

## Docker and Git

Current Compose passes some existing application/DB secrets through environment
variables. Docker-daemon users can inspect them and mounts. File mode `0600` does
not protect against Docker/root access. No platform-wide secret redesign is implied.
Docker build contexts exclude env files, credential folders, private-key extensions
and backups. Use selective Git staging; ignored files can still be force-added.

Dedicated SSH key: `~/.ssh/id_ed25519_github_cs2`, `0600`; scoped `Host github.com`
configuration, no global SSH changes. The key is unencrypted for server use, so
host-account protection is essential. Add only its `.pub` to GitHub Settings >
SSH and GPG keys. The private key must never leave this host or enter Git.
GitHub host keys were checked against the
[official fingerprints](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints).

Push only after `ssh -T git@github.com` identifies the expected account, the remote
is verified, the tree is clean, divergence checked and a bundle verified. No force
push, credential URL or automatic history rewrite. V0.12 leaves the existing HTTPS
remote unchanged until SSH authentication actually succeeds.
