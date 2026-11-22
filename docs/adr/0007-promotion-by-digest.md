# ADR-0007: Promote images by digest through a bot pull request

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

Every merge to main builds, scans, pushes and signs the api and web images. Until now the new digests
reached `deploy/overlays/local` by hand: someone copied them from the release log into a pull request.
That copy was the only manual step between a merge and a deployment, and the easiest one to get wrong
or forget.

## Decision

- **Images are referenced by digest, not by tag.** A tag can be moved to another image; a digest is the
  hash of the image content and cannot. The signature is made on the digest as well, so the manifest
  names exactly the image that was signed.
- **A bot opens a pull request; it never pushes to main.** The `promote` job in `release.yml` runs after
  the release job, rewrites the two digests with `kustomize edit set image` and opens a PR. The PR runs
  the same checks as any other change, main keeps the same ruleset, and the history shows who changed
  what. Merging stays a human decision.
- **The bot is a GitHub App.** A pull request opened with `GITHUB_TOKEN` creates its workflow runs in an
  approval-required state, so every promotion would wait for a manual click. GitHub recommends an App
  installation token for this case. The App has two permissions (Contents and Pull requests, read and
  write) and is installed on this repository only.
- **No loop.** `release.yml` ignores changes under `deploy/`, so merging a bot PR builds no image and
  opens no new bot PR. Changes under `docs/` and Markdown files are ignored as well: they are not part of
  any image.

## Consequences

- The App's private key is the repository's only long-lived CI secret (`BOT_PRIVATE_KEY`). Only the
  `promote` job on main uses it. Each run exchanges it for an installation token that expires after one
  hour and is revoked when the job ends. A leaked key reaches one repository with two permissions;
  rotating it means generating a new key and deleting the old one.
- The `promote` job's own `GITHUB_TOKEN` has no permissions; every write goes through the App token.
- Every release opens a bot PR, including releases that only changed pipeline files, because each build
  produces a new digest.
- `kustomize edit` rewrites the whole file in its own format. The first bot PR reformatted
  `deploy/overlays/local/kustomization.yaml`; later ones change only the digest lines.
- Tag builds (`v*.*.*`) are not promoted; only main builds reach the local overlay.

## Sources

- `GITHUB_TOKEN` and workflow runs: https://docs.github.com/en/actions/concepts/security/github_token
- Installation token lifetime: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app
- Token action used by the `promote` job: https://github.com/actions/create-github-app-token
