## 📋 PR Checklist

Before submitting, make sure you fulfil the following:

- [ ] My skill lives at `skills/<id>/<id>.md` (canonical path, `id` == folder name)
- [ ] Frontmatter contains `id`, `file_path`, `category`, `tags`, `description` (non-empty)
- [ ] File has no UTF-8 BOM and no truncated "…" marker
- [ ] All five required sections are present (`System Architecture`, `Data Contracts`, `Production Reference Implementation`, `Execution Protocol`, `Edge Cases`)
- [ ] Reference implementation is complete and runnable
- [ ] `npm run build` regenerates cleanly and `npm run ci` passes
- [ ] `registry.json` + regenerated `.opencode/skills/` are committed
- [ ] README catalog row (if new skill) is included

## What does this PR do?

<!-- Summary of your change -->

## Related issues

<!-- Fixes #123 -->

## Screenshots / demos (if applicable)

<!-- paste outputs here -->