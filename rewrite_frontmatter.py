#!/usr/bin/env python3
import os, re

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
    
    # Find ALL --- delimited frontmatter blocks
    # Pattern: --- followed by content, followed by ---
    blocks = []
    remaining = content
    while True:
        start = remaining.find('\n---')
        if start == -1:
            break
        # The --- might be on its own line at the start
        if remaining.startswith('---'):
            # Handle file starting with ---
            ft_end = remaining.find('\n---', 3)
            if ft_end == -1:
                break
            ft_content = remaining[3:ft_end].strip()
            blocks.append(ft_content)
            remaining = remaining[ft_end + 1:]  # Skip past \n---
        else:
            # --- not at start, find it
            ft_end = remaining.find('\n---', 1)
            if ft_end == -1:
                break
            ft_content = remaining[1:ft_end].strip()  # skip the leading char before ---
            blocks.append(ft_content)
            remaining = remaining[ft_end + 1:]
    
    if len(blocks) >= 2:
        # There are two frontmatter blocks. Keep the SECOND one (original) and discard the first (migration-added)
        # The second block starts after the first ---...--- sequence
        # Find position of second block in original content
        
        # Strategy: find the position after the first block's closing ---
        # First block ends at: content start + length of first block + delimiters
        
        # Let's just locate the second ---...--- sequence
        # Pattern: ---\n...content...\n---
        
        # Find all positions of --- lines
        lines = content.split('\n')
        demarcation_indices = [i for i, line in enumerate(lines) if line.strip() == '---']
        
        if len(demarcation_indices) >= 4:  # Two blocks = 4 delimiters
            # Block 1: lines[demarcation_indices[0] : demarcation_indices[1]+1]
            # Block 2: lines[demarcation_indices[2] : demarcation_indices[3]+1]
            
            # Keep block 2 (original) and body after it
            # Body starts after line demarcation_indices[3]
            body_start_line = demarcation_indices[3] + 1
            body = '\n'.join(lines[body_start_line:])
            
            # Frontmatter to keep is lines[demarcation_indices[2] : demarcation_indices[3]+1]
            ft_lines = lines[demarcation_indices[2]:demarcation_indices[3]+1]
            frontmatter = '\n'.join(ft_lines)
            
            # Reconstruct: frontmatter + newline + body
            new_content = frontmatter + '\n' + body
            
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            fixed += 1
            if fixed <= 3:
                print(f"Fixed: {dir_name}")
                # Verify
                with open(md_file, 'r', encoding='utf-8') as fv:
                    vcontent = fv.read()
                vcount = vcontent.count('---')
                print(f"  --- count after: {vcount}")
    else:
        # Only one block - check if it's the migration-added empty one
        # or the original. If the category is "uncategorized" and tags are empty,
        # it's the migration-added one - remove it
        if 'category: uncategorized' in content and 'tags: []' in content:
            # This is the migration-added frontmatter; remove it
            # Find and remove the first ---...--- block
            # Keep everything after the first ---
            first_ft_end = content.find('\n---', 3)
            if first_ft_end != -1:
                # Keep from after the first --- block
                remaining_after = content[first_ft_end + 1:]
                # But we also need to handle the second --- that might be left
                # Actually, let's just remove the first block
                lines = remaining_after.split('\n', 1)  # split on first newline
                # The first line might be just '---' from the second block
                # Let's be more careful
                
                # Count --- markers
                if content.count('---') >= 2:
                    # Remove the very first --- block
                    # Find first ---...---
                    first_block_end = content.find('\n---', 3)
                    if first_block_end != -1:
                        # Keep from after first ---...---
                        rest = content[first_block_end + 1:]
                        # Now there might be a leftover --- at the start
                        # Just write the rest
                        with open(md_file, 'w', encoding='utf-8') as f:
                            f.write(rest)
                        fixed += 1
                        if fixed <= 3:
                            print(f"Fixed (remove migration): {dir_name}")
                else:
                    # Only one --- block, nothing to do
                    pass

print(f"Total files fixed: {fixed}")