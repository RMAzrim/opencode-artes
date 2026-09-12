---
name: github-actions-generator
description: Design automated CI/CD workflows for testing, building, and deployment.
metadata:
  source: skills/github-actions-generator/github-actions-generator.md
---

# GitHub Actions Generator

## Prerequisites & Dependencies
- GitHub repository with write access; workflow files live under `.github/workflows/`
- GitHub Actions enabled; required secrets provisioned (registry tokens, cloud credentials, or OIDC role trust)
- `act` (optional) for local dry-runs: `brew install act` / `scoop install act`

## Execution Steps
1. Map the delivery pipeline: triggers (`push` to main, `pull_request`, `workflow_dispatch`) and stages lint -> test -> build -> deploy.
2. Write CI jobs with pinned action versions (SHA pinning for third-party actions), language version matrix, and dependency caching via `setup-*` built-in cache.
3. Gate deploy jobs with `needs`, restrict them to protected branches via `if:`, and attach an environment with required reviewers.
4. Keep credentials in repository/environment secrets only; prefer short-lived OIDC tokens (`permissions: id-token: write`) over long-lived keys.
5. Validate locally (`act pull_request`), push a branch, and confirm all checks go green end-to-end.
6. Add status badges and branch protection rules requiring the workflow checks to pass before merge.

```yaml
name: ci-cd
on:
  push: { branches: [main] }
  pull_request:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix: { node: [18, 20] }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "${{ matrix.node }}", cache: npm }
      - run: npm ci
      - run: npm run lint
      - run: npm test -- --coverage

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    permissions: { id-token: write, contents: read }
    steps:
      - uses: actions/checkout@v4
      - run: echo "deploy step (registry push / cloud deploy) here"
```

```bash
act pull_request -j test
```

