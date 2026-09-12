#!/usr/bin/env node
/**
 * build-registry.js
 * 
 * Recursively scans the skills directory and extracts frontmatter
 * to generate registry.json with all registered skills.
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.join(__dirname, '..');
const SKILLS_DIR = path.join(PROJECT_ROOT, 'skills');
const REGISTRY_PATH = path.join(PROJECT_ROOT, 'registry.json');
const OPENCODE_SKILLS_DIR = path.join(PROJECT_ROOT, '.opencode', 'skills');

/**
 * Parses YAML frontmatter from a markdown file.
 * Looks for --- delimited frontmatter at the start of the file.
 * 
 * @param {string} content - Full file content
 * @returns {object} Parsed frontmatter keys/values
 */
function parseFrontmatter(content) {
  const frontmatter = {};
  
  if (!content.startsWith('---')) {
    return frontmatter;
  }
  
  const nextDelimiterIndex = content.indexOf('---', 3);
  if (nextDelimiterIndex === -1) {
    return frontmatter;
  }
  
  const frontmatterText = content.substring(3, nextDelimiterIndex);
  const lines = frontmatterText.split('\n');
  
  for (const line of lines) {
    const colonIndex = line.indexOf(':');
    if (colonIndex === -1) continue;
    
    const key = line.substring(0, colonIndex).trim();
    const value = line.substring(colonIndex + 1).trim();
    
    // Remove surrounding quotes if present
    if ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))) {
      frontmatter[key] = value.substring(1, value.length - 1);
    } else {
      frontmatter[key] = value;
    }
  }
  
  return frontmatter;
}

/**
 * Parses a tags value into an array of tag strings.
 * Handles YAML flow-list syntax such as `[a, b, c]` (including quoted
 * elements like `["a", "b"]`), a plain comma-separated list `a, b, c`,
 * and empty values `[]` or `` which both resolve to an empty array.
 *
 * @param {string|Array} value - Raw tags value as stored by parseFrontmatter
 * @returns {Array} Array of trimmed tag strings
 */
function parseTags(value) {
  if (Array.isArray(value)) return value;
  if (typeof value !== 'string' || value.trim() === '') return [];

  let v = value.trim();

  if (v.startsWith('[') && v.endsWith(']')) {
    v = v.slice(1, -1).trim();
  }

  if (v === '') return [];

  return v
    .split(',')
    .map(t => t.trim().replace(/^["']|["']$/g, ''))
    .filter(Boolean);
}

/**
 * Recursively scans the skills directory for all skill markdown files.
 * Expects the structure: ./skills/<skill-id>/<skill-id>.md
 * 
 * @returns {Array} Array of skill objects for registry
 */
function scanSkillsDirectory() {
  const skills = [];
  
  if (!fs.existsSync(SKILLS_DIR)) {
    console.error(`Skills directory not found: ${SKILLS_DIR}`);
    return skills;
  }
  
  // Read all first-level directories in skills/
  const dirs = fs.readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory());
  
  for (const dir of dirs) {
    const dirPath = path.join(SKILLS_DIR, dir.name);
    const mdFile = path.join(dirPath, `${dir.name}.md`);
    
    if (fs.existsSync(mdFile)) {
      const rawContent = fs.readFileSync(mdFile, 'utf-8');
      const frontmatter = parseFrontmatter(rawContent);
      
      skills.push({
        id: frontmatter.id || dir.name,
        file_path: path.relative(PROJECT_ROOT, mdFile).split(path.sep).join('/'),
        name: frontmatter.name || dir.name,
        category: frontmatter.category || 'uncategorized',
        tags: parseTags(frontmatter.tags),
        author: frontmatter.author || 'opencode-core',
        version: frontmatter.version || '1.0.0',
        description: frontmatter.description || ''
      });
    }
  }
  
  return skills;
}

const INDICATOR_START = /^[-?:,[\]{}#&*!|>'"%@`]/;

/**
 * Serializes a scalar value into safe YAML.
 * Returns the value unchanged when it is a plain scalar (no leading YAML
 * indicator, no leading/trailing whitespace, no `: `, ` #`, newline or tab),
 * otherwise JSON.stringify (a double-quoted YAML scalar).
 *
 * @param {string} value - Raw value
 * @returns {string} YAML-safe scalar rendering
 */
function yamlScalar(value) {
  const v = String(value);
  if (!INDICATOR_START.test(v) && !/^\s|\s$/.test(v) && !/: | #|\n|\t/.test(v)) {
    return v;
  }
  return JSON.stringify(v);
}

/**
 * Extracts the markdown body that follows a --- delimited frontmatter block.
 *
 * @param {string} content - Full file content
 * @returns {string} Body content (without leading blank lines)
 */
function extractBody(content) {
  if (!content.startsWith('---')) return content;

  const closingDelimiter = content.indexOf('---', 3);
  if (closingDelimiter === -1) return content;

  return content.slice(closingDelimiter + 3).trimStart();
}

/**
 * Generates OpenCode-discoverable SKILL.md files from the canonical skill
 * sources. OpenCode loads skills from .opencode/skills/<id>/SKILL.md. The
 * skill ID is path-derived (the folder name); frontmatter `name` is only a
 * display label (the canonical human-readable name) and `description` must be
 * non-empty for the skill to be advertised. The canonical skills/<id>/<id>.md
 * file remains the single source of truth; this function maps it to OpenCode's
 * format.
 *
 * @param {Array} skills - Skill objects from scanSkillsDirectory()
 * @returns {number} Number of SKILL.md files generated
 */
function generateOpenCodeSkills(skills) {
  let count = 0;

  for (const skill of skills) {
    const sourceFile = path.join(SKILLS_DIR, skill.id, `${skill.id}.md`);
    if (!fs.existsSync(sourceFile)) continue;

    const content = fs.readFileSync(sourceFile, 'utf-8');
    const body = extractBody(content);
    const skillDir = path.join(OPENCODE_SKILLS_DIR, skill.id);
    fs.mkdirSync(skillDir, { recursive: true });

    const sk = [
      '---',
      `name: ${yamlScalar(skill.name)}`,
      `description: ${yamlScalar(skill.description)}`,
      'metadata:',
      `  source: ${skill.file_path}`,
      '---',
      '',
      body,
      ''
    ].join('\n');

    fs.writeFileSync(path.join(skillDir, 'SKILL.md'), sk);
    count++;
  }

  return count;
}

/**
 * Main execution
 */
try {
  const skills = scanSkillsDirectory();
  
  // Write registry.json
  const registry = skills;
  fs.writeFileSync(REGISTRY_PATH, JSON.stringify(registry, null, 2));
  
  console.log(`Registry generated successfully: ${skills.length} skills`);
  console.log(`Output: ${REGISTRY_PATH}`);

  // Generate .opencode/skills/<id>/SKILL.md for OpenCode discovery
  const generated = generateOpenCodeSkills(skills);
  console.log(`OpenCode skills generated: ${generated}`);
  console.log(`Output: ${OPENCODE_SKILLS_DIR}`);
  
} catch (error) {
  console.error('Error generating registry:', error.message);
  process.exit(1);
}