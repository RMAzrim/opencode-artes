# Security Policy

## Reporting a vulnerability

`opencode-artes` is a collection of local AI-agent skills. If you find a weakness — in a skill's reference implementation, in the build tooling, or in dependency usage — please **do not open a public issue**. Report it privately instead:

- Open a [private security advisory](https://github.com/RMAzrim/opencode-artes/security/advisories/new)
- Or email the maintainer via the contact link on your GitHub profile

We aim to acknowledge reports within **72 hours** and to ship a patched upstream skill as soon as a fix is ready. You will be credited in the advisory and release notes unless you prefer to stay anonymous.

## Scope

- Distribution repo: `RMAzrim/opencode-artes` and all tagged releases
- Generated artifacts (`registry.json`, `.opencode/skills/`) produced by `npm run build`
- Every skill's `## 3. Production Reference Implementation` code

## Out of scope

- Behavior of the OpenCode agent product itself (report at https://github.com/anomalyco/opencode/issues)
- Skills from third-party sources mirrored here — report to their upstream instead

## Local legitimacy note

Several skills in this repo perform **security testing against your own localhost code** (CVE audit, SAST, SQLi/XSS payload tests, JWT secret cracking, IDOR/BOLA scans). They are defensive tooling for **your own applications and locally running servers only**. Never point them at systems you do not own or lack explicit authorization to test. Misuse is on the operator.

## Supported versions

The latest release on `main` is always the supported version. We do not maintain backported security patches for older tags — upgrade to the newest release.