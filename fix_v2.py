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
    
    # Check if this file has the migration-added frontmatter:
    # - category: uncategorized
    # - tags: []  
    # - description: (empty or very short)
    # - name is lowercase with hyphens (no spaces)
    
    has_migration_ff = False
    if 'category: uncategorized' in content:
        # Extract the first frontmatter block
        # Find first ---...---
        first_block_start = content.find('---\n')
        if first_block_start != -1:
            # Find the closing ---
            first_block_end = content.find('\n---', first_block_start + 3)
            if first_block_end != -1:
                first_block = content[first_block_start:first_block_end]
                # Check if it has the migration markers
                if 'tags: []' in first_block and 'description: ' in first_block:
                    # This is the migration-added frontmatter - remove it
                    has_migration_ff = True
    
    if has_migration_ff:
        # Remove the first frontmatter block (from after the opening --- to the closing ---)
        # The first block is from position 0 to the first \n--- closing
        # Actually, the file starts with ---, so:
        # Line 1: ---
        # Lines 2-N: frontmatter content
        # Then \n---
        
        # Find the end of the first frontmatter block
        # There might be two --- sequences: the migration one and the original one
        # Let me find all --- positions
        import re
        demarcations = [m.start() for m in re.finditer(r'^---$', content, re.MULTILINE)]
        
        if len(demarcations) >= 2:
            # Keep content after the SECOND --- block
            # The second --- block is the original frontmatter we want to keep
            # But wait - we want to REMOVE the migration-added one and keep the original
            
            # Actually, let me reconsider. The file structure is:
            # --- [migration block]
            # --- [original block]
            # body
            
            # Or it might be:
            # --- [original block]
            # body
            
            # Let me just check: does the content after the first ---...--- have proper frontmatter?
            
            # Simpler approach: just find the original frontmatter by looking for
            # 'category: frontend' or similar patterns, and keep from there
            
            # Let me use a different strategy: just rewrite the file keeping only
            # the block that has actual skill-related content
            
            # Find position after first ---...---
            first_close = content.find('\n---', 3)
            if first_close != -1:
                # Get content after first closing ---
                after_first = content[first_close + 1:]
                
                # Now check if after_first starts with another --- block
                if after_first.startswith('---\n'):
                    # There are two blocks. The second one is the original.
                    # But we need to figure out where the second --- closes
                    second_open = after_first.find('\n---', 3)
                    if second_close := after_first.find('\n---', second_open + 3 if second_open else 3):
                        # Keep from after the second --- block
                        final_content = after_first[second_close + 1:]
                        with open(md_file, 'w', encoding='utf-8') as f:
                            f.write(final_content)
                        fixed += 1
                        if fixed <= 5:
                            print(f"Fixed: {dir_name}")
                else:
                    # Only one --- block; if it's the migration one, remove it
                    # Check if this is the migration pattern
                    if 'category: uncategorized' in content.split('\n---')[1] if '\n---' in content else False:
                        # Remove first block, keep rest
                        after_first = content[first_close + 1:]
                        with open(md_file, 'w', encoding='utf-8') as f:
                            f.write(after_first)
                        fixed += 1
                        if fixed <= 5:
                            print(f"Fixed (simple): {dir_name}")
    
print(f"Total files fixed: {fixed}")