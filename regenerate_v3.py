#!/usr/bin/env python3
import json, os, re

skills_dir = r'C:\Users\ACER\opencode-artes\skills'
registry = []

for dir_name in sorted(os.listdir(skills_dir)):
    dir_path = os.path.join(skills_dir, dir_name)
    if not os.path.isdir(dir_path):
        continue
    
    md_file = os.path.join(dir_path, f'{dir_name}.md')
    if not os.path.exists(md_file):
        continue
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all --- line positions (standalone --- on a line)
    lines = content.split('\n')
    demarcation_indices = [i for i, line in enumerate(lines) if line.strip() == '---']
    
    frontmatter = {}
    
    if len(demarcation_indices) >= 4:
        # Two frontmatter blocks: keep the SECOND one
        # Block 1: lines[demarcation_indices[0] : demarcation_indices[1]+1]
        # Block 2: lines[demarcation_indices[2] : demarcation_indices[3]+1]
        
        # Parse the SECOND frontmatter block
        second_ft_lines = lines[demarcation_indices[2]+1:demarcation_indices[3]]
        second_ft_text = '\n'.join(second_ft_lines)
        
        for line in second_ft_text.strip().split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                k, v = line.split(':', 1)
                frontmatter[k.strip()] = v.strip().strip('"').strip("'")
    elif len(demarcation_indices) >= 2:
        # Single frontmatter block - parse it
        ft_lines = lines[demarcation_indices[0]+1:demarcation_indices[1]]
        ft_text = '\n'.join(ft_lines)
        for line in ft_text.strip().split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                k, v = line.split(':', 1)
                frontmatter[k.strip()] = v.strip().strip('"').strip("'")
    elif content.startswith('---'):
        # Edge case: file starts with --- but only one block
        # Try to parse minimally
        close_idx = content.find('\n---', 3)
        if close_idx != -1:
            ft_text = content[3:close_idx]
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
from collections import Counter
cats = Counter(r['category'] for r in registry)
for cat, count in sorted(cats.items()):
    print(f'  {cat}: {count}')
print(f"Total: {sum(cats.values())}")