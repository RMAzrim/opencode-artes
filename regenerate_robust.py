#!/usr/bin/env python3
import json, os

skills_dir = r'C:\Users\ACER\opencode-artes\skills'
registry = []

# Robust registry generation: only parse the FIRST ---...--- block at file start
for dir_name in sorted(os.listdir(skills_dir)):
    dir_path = os.path.join(skills_dir, dir_name)
    if not os.path.isdir(dir_path):
        continue
    
    md_file = os.path.join(dir_path, f'{dir_name}.md')
    if not os.path.exists(md_file):
        continue
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Only parse frontmatter if file starts with ---
    frontmatter = {}
    if content.startswith('---'):
        # Find the closing --- of the first block
        # Look for \n--- after the opening ---
        close_idx = content.find('\n---', 3)
        if close_idx != -1:
            ft_text = content[3:close_idx]
            # Parse key:value pairs
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

# Print category breakdown - let me count manually
from collections import Counter
# Read the registry to count
cats = Counter(r['category'] for r in registry)
for cat, count in sorted(cats.items()):
    print(f'  {cat}: {count}')
print(f"Total: {sum(cats.values())}")