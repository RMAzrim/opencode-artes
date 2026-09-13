'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, '.opencode', 'skills');
const DST = path.join(ROOT, 'docs', 'skills');

function copyDir(from, to) {
  if (!fs.existsSync(from)) {
    console.error(`error: ${from} missing. Run \`npm run build\` first.`);
    process.exit(1);
  }
  fs.rmSync(to, { recursive: true, force: true });
  fs.mkdirSync(to, { recursive: true });
  let copied = 0;
  for (const skill of fs.readdirSync(from, { withFileTypes: true })) {
    if (!skill.isDirectory()) continue;
    const srcSkill = path.join(from, skill.name);
    const dstSkill = path.join(to, skill.name);
    fs.mkdirSync(dstSkill, { recursive: true });
    for (const f of fs.readdirSync(srcSkill)) {
      fs.copyFileSync(path.join(srcSkill, f), path.join(dstSkill, f));
      copied++;
    }
  }
  return copied;
}

const files = copyDir(SRC, DST);
console.log(`Published ${files} generated SKILL.md copies to docs/skills/ (served by GitHub Pages).`);