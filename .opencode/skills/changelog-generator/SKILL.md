---
name: changelog-generator
description: Parse Git commit logs to generate a CHANGELOG.md adhering to Conventional Commits.
metadata:
  source: skills/changelog-generator/changelog-generator.md
---

# Changelog Generator

## Prerequisites & Dependencies
- Git repository with Conventional Commits (`feat:`, `fix:`, `feat!:` / `BREAKING CHANGE:` …)
- `git-cliff` 2.x or Node 18+ with `npm i -D conventional-changelog-cli`
- Semantic tags present (`vX.Y.Z`) marking release boundaries

## Execution Steps
1. Validate history hygiene: list non-conventional commits since the last tag (`git log $(git describe --tags --abbrev=0)..HEAD --oneline`) and fix noteworthy ones via rebase before generating.
2. Determine the next version from commit types: breaking → major, `feat` → minor, only `fix`/`chore` → patch.
3. Generate the changelog since the last tag with the chosen tool, mapping types to sections (Features / Bug Fixes / Breaking Changes).
4. Prepend the new section at the top of the existing CHANGELOG.md and edit or regenerate the `[Unreleased]` link references.
5. Review output wording: remove noise commits (chore: bump deps), link to issues/PRs, and reorder breaking changes up front.
6. Commit `CHANGELOG.md`, create the release tag, and derive GitHub Release notes from the same section.

```bash
git log "$(git describe --tags --abbrev=0)..HEAD" --oneline --no-merges

# git-cliff (config: cliff.toml)
git cliff --tag v1.4.0 --prepend CHANGELOG.md

# conventional-changelog
npx conventional-changelog -p angular -i CHANGELOG.md -s -r 0
```

## Output Example

```markdown
## [1.4.0] - 2026-09-09
### Breaking
- api: remove deprecated /v1/login endpoint (#312)
### Features
- orders: support bulk cancellation (#305)
### Bug Fixes
- payments: retry idempotent charges on gateway timeout (#318)
```
```
