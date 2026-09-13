'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const REGISTRY = path.join(ROOT, 'registry.json');
const OWNER_REPO = 'RMAzrim/opencode-artes';

function main() {
  if (!fs.existsSync(REGISTRY)) {
    console.error('error: registry.json not found. Run `npm run build` first.');
    process.exit(1);
  }

  const skills = JSON.parse(fs.readFileSync(REGISTRY, 'utf-8'));
  if (!Array.isArray(skills)) {
    console.error('error: registry.json is not an array.');
    process.exit(1);
  }

  const count = skills.length;
  const description =
    `opencode-artes: ${count} production-grade OpenCode skills for fullstack web ` +
    'development, localhost security auditing and AI agent automation. Frontend, ' +
    'backend, devops, testing and AI-ops skill ecosystem in one place.';

  const res = spawnSync('gh', ['repo', 'edit', OWNER_REPO, '--description', description], {
    stdio: 'inherit',
  });

  if (res.error) {
    console.error(`error: could not run gh (${res.error.message}). Is GitHub CLI installed and authenticated?`);
    process.exit(1);
  }
  if (res.status !== 0) {
    console.error(`error: gh repo edit exited with code ${res.status}`);
    process.exit(res.status || 1);
  }

  console.log(`GitHub description updated: ${count} skills`);
}

main();