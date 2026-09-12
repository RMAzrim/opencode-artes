#!/usr/bin/env node
/**
 * build-registry.js
 * 
 * Recursively scans the skills directory and extracts frontmatter
 * to generate registry.json with all registered skills.
 */

const fs = require('fs');
const path = require('path');

const SKILLS_DIR = path.join(__dirname, '..', 'skills');
const REGISTRY_PATH = path.join(__dirname, '..', 'registry.json');

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
        file_path: path.relative(__dirname, mdFile),
        name: frontmatter.name || dir.name,
        category: frontmatter.category || 'uncategorized',
        tags: frontmatter.tags ? (Array.isArray(frontmatter.tags) ? frontmatter.tags : frontmatter.tags.split(',').map(t => t.trim())) : [],
        author: frontmatter.author || 'opencode-core',
        version: frontmatter.version || '1.0.0',
        description: frontmatter.description || ''
      });
    }
  }
  
  return skills;
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
  
} catch (error) {
  console.error('Error generating registry:', error.message);
  process.exit(1);
}