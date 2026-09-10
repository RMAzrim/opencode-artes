---
id: secrets-leak-detector
file_path: skills/secrets-leak-detector.md
name: Secrets Leak Detector
category: security
tags: [secrets-detection, gitleaks, trufflehog, credential-rotation, code-audit]
author: opencode-core
version: 1.0.0
description: Scan codebases to detect leaked API keys, tokens, or credentials.
---

# Secrets Leak Detector

## Prerequisites & Dependencies
- `gitleaks` 8.x and/or `trufflehog` 3.x on `PATH`; Git access to the full repository history
- Optional: `pre-commit` (Python) for local hook-based scanning
- Incident response access: authority to revoke/rotate credentials for any confirmed finding

## Execution Steps
1. Run a no-git scan on the working tree to catch unstaged leaks: `gitleaks detect --no-git -v`.
2. Scan the entire Git history, including deleted branches: `gitleaks detect --log-opts="--all"` (optionally `--redact` on shared terminals).
3. Cross-check with Trufflehog verification to reduce false positives: `trufflehog git file://. --only-verified`.
4. Triage findings: classify valid vs revoked, record commit hash, author, and file path; never paste secret values into tickets or reports.
5. Rotate every exposed credential immediately — treat all detected secrets as compromised regardless of age.
6. Purge secrets from history with `git filter-repo` (force-push with team coordination), then add a pre-commit scan and a `.gitleaks.toml` allowlist for sanctioned test fixtures.

```bash
gitleaks detect --no-git --verbose --report-format json --report-path leaks.json
gitleaks detect --log-opts="--all" --verbose --redact
trufflehog git file://. --only-verified --json > truffle.json

pip install git-filter-repo
git filter-repo --replace-text secrets-to-redact.txt --force
```

```toml
# .gitleaks.toml
[allowlist]
paths = ['''(^|/)test/fixtures/.*''']
```
