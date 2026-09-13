#!/usr/bin/env python3
import os

skills_dir = r'C:\Users\ACER\opencode-artes\skills'

fixed = 0
for dir_name in sorted(os.listdir(skills_dir)):
    dir_path = os.path.join(skills_dir, dir_name)
    if not os.path.isdir(dir_path):
        continue
    
    md_file = os.path.join(dir_path, f'{dir_name}.md')
    if not os.path.exists(md_file):
        continue
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split content by '---' delimiter
    parts = content.split('---')
    
    if len(parts) >= 3:
        # Keep the second frontmatter (index 1) and the body (from index 2 onwards)
        frontmatter = parts[1].strip()
        body = '---'.join(parts[2:])
        
        new_content = f'---\n{frontmatter}\n---\n{body}'
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        fixed += 1

print(f"Total files cleaned: {fixed}")