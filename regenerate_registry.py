#!/usr/bin/env python3
import json, os, glob
from collections import Counter

skills_dir = r'C:\Users\ACER\opencode-artes\skills'
registry = []

# Recursively scan skills/*/*.md - the new nested structure
for dir_name in sorted(os.listdir(skills_dir)):
    dir_path = os.path.join(skills_dir, dir_name)
    if not os.path.isdir(dir_path):
        continue
    
    md_file = os.path.join(dir_path, f'{dir_name}.md')
    if not os.path.exists(md_file):
        continue
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse simple YAML frontmatter: find between --- markers
    frontmatter = {}
    if content.startswith('---'):
        parts = content.split('\n---', 1)
        if len(parts) >= 2:
            ft_text = parts[1]
            # Find the closing ---
            remaining = parts[1]
            if '---' in remaining:
                close_parts = remaining.split('---', 1)
                ft_text = close_parts[0]  # Content before second ---
            
            for line in ft_text.strip().split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    k, v = line.split(':', 1)
                    frontmatter[k.strip()] = v.strip().strip('"').strip("'")
    
    # Build registry entry
    entry = {
        'id': frontmatter.get('id', dir_name),
        'file_path': f'skills/{dir_name}/{dir_name}.md',
        'name': frontmatter.get('name', dir_name),
        'category': frontmatter.get('category', 'uncategorized'),
        'tags': frontmatter.get('tags', '[]'),
        'author': frontmatter.get('author', 'opencode-core'),
        'version': frontmatter.get('version', '1.0.0'),
        'description': frontmatter.get('description', '')
    }
    registry.append(entry)

# Write registry.json
with open(r'C:\Users\ACER\opencode-artes\registry.json', 'w', encoding='utf-8') as f:
    json.dump(registry, f, indent=2, ensure_ascii=False)

print(f'Registry generated: {len(registry)} skills')
# Print category breakdown
cats = Counter(r['category'] for r in registry)
for cat, count in sorted(cats.items()):
    print(f'  {cat}: {count}')