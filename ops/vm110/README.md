# VM110 Kyoo 5.3.0 integration

Upstream baseline: `v5.3.0` / `77a986123bae41379b63a217b5331b2f34f6dd93`.

The service-specific `Dockerfile.vm110` files rebuild this integration against pinned official 5.3.0 runtime images. The build checks frontend/API types, pagination and list policy, empty preparation responses, and verified playback access. Scanner tests additionally require a separate PostgreSQL database to enable the temporary-table queue regressions.

Retained deployment behavior:

- Skip missing TVDB season translations and continue with available languages.
- Claim exactly one scanner request; resume queued work after reconnect and periodically.
- Restrict targeted NFS cleanup to its selected directory and support reidentifying existing files.
- Preserve HTTPS pagination links, individual-title listing defaults and mobile viewport backgrounds.
- Honor the new collection display preference; use the existing individual-title policy when enabled.
- Require both `verified=true` and `core.play` for playback.
- Accept the transcoder's empty 202 preparation response.

Chapter behavior follows official 5.3.0. This branch contains no custom chapter worker, job API, polling settings, or migration 6. Existing standard chapter metadata and fingerprints are retained. Before moving an existing custom database from schema 6 to 5, stop writers, make and verify a complete backup, and remove only the custom job table and `info.ver_chapters` column in a transaction. Do not change the migration marker without handling its schema changes.

The 5.3.0 auth migrations hash sessions/API keys and persist presigns. A rollback must restore the matching database snapshot as well as the old images and settings.

VM110 deployment records, protected settings and backups are stored on the server under `/opt/kyoo-deployments/20261108-v5.3.0/`. Secrets and database dumps are deliberately kept outside Git.

