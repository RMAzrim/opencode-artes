'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SKILLS_DIR = path.join(ROOT, 'skills');
const GENERATED_DIR = path.join(ROOT, '.opencode', 'skills');
const REGISTRY = path.join(ROOT, 'registry.json');

const REQUIRED_FIELDS = ['id', 'file_path', 'category', 'tags', 'description'];

function fail(msg) {
  console.error(`\u2717 ${msg}`);
}

function ok(msg) {
  console.log(`\u2713 ${msg}`);
}

function main() {
  let failures = 0;

  if (!fs.existsSync(SKILLS_DIR)) {
    console.error('error: skills/ directory missing');
    process.exit(1);
  }

  const skillDirs = fs
    .readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort();

  if (skillDirs.length !== new Set(skillDirs).size) {
    fail('duplicate skill directories found');
    failures++;
  }

  let registryCount = 0;
  let registry = [];
  if (fs.existsSync(REGISTRY)) {
    try {
      registry = JSON.parse(fs.readFileSync(REGISTRY, 'utf-8'));
      registryCount = registry.length;
    } catch (e) {
      fail(`registry.json is invalid JSON: ${e.message}`);
      failures++;
    }
  } else {
    fail('registry.json missing');
    failures++;
  }

  if (fs.existsSync(REGISTRY) && registryCount !== skillDirs.length) {
    fail(`registry count (${registryCount}) != skills dir count (${skillDirs.length}). Run \`npm run build\`.`);
    failures++;
  }

  for (const id of skillDirs) {
    const canDir = path.join(SKILLS_DIR, id);
    if (!fs.existsSync(canDir)) continue;
    const mdFiles = fs.readdirSync(canDir).filter((f) => f.endsWith('.md'));
    if (mdFiles.length < 1) {
      fail(`skill ${id}: no canonical markdown file`);
      failures++;
      continue;
    }
    for (const f of mdFiles) {
      const filePath = path.join(canDir, f);
      const src = fs.readFileSync(filePath, 'utf-8');
      if (src.charCodeAt(0) === 0xfeff) {
        fail(`skill ${id}/${f}: file has a UTF-8 BOM`);
        failures++;
      }
      const fm = src.match(/^---\r?\n([\s\S]*?)\r?\n---/);
      if (!fm) {
        fail(`skill ${id}/${f}: missing YAML frontmatter`);
        failures++;
        continue;
      }
      const body = fm[1];
      const fieldRe = (k) => body.match(new RegExp(`^${k}:`, 'm'));
      for (const k of REQUIRED_FIELDS) {
        if (!fieldRe(k)) {
          fail(`skill ${id}/${f}: missing frontmatter field "${k}"`);
          failures++;
        }
      }
      const idMatch = body.match(/^id:\s*(.+)/m);
      if (idMatch && idMatch[1].trim() !== id) {
        fail(`skill ${id}/${f}: frontmatter id "${idMatch[1].trim()}" != folder id "${id}"`);
        failures++;
      }
      const gen = path.join(GENERATED_DIR, id, 'SKILL.md');
      if (!fs.existsSync(gen)) {
        fail(`skill ${id}: generated .opencode/skills/${id}/SKILL.md missing. Run \`npm run build\`.`);
        failures++;
      }
    }
  }

  if (registry.length) {
    const registryIds = new Set(registry.map((s) => s.id));
    const missingInRegistry = skillDirs.filter((id) => !registryIds.has(id));
    if (missingInRegistry.length) {
      fail(`skills missing from registry.json: ${missingInRegistry.join(', ')}. Run \`npm run build\`.`);
      failures++;
    }
  }

  if (failures > 0) {
    console.error(`\nerror: CI verification failed with ${failures} issue(s).\n`);
    process.exit(1);
  }

  ok(`verified ${skillDirs.length} skills`);
  ok(`registry.json consistent (${registryCount} entries)`);
  ok('generated .opencode/skills/ copies present for all skills');
  ok('frontmatter contract (id, path, category, tags, description) satisfied');
  console.log('\nCI verification passed.');
}

main();