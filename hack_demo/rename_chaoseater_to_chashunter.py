#!/usr/bin/env python3
"""
Python script to rename ChaosHunter to ChaosHunter
Run this script from the project root directory
"""

import os
import re
import glob
from pathlib import Path

def rename_in_files():
    """Rename all occurrences of ChaosHunter to ChaosHunter in code files"""
    
    print("Starting ChaosHunter to ChaosHunter rename process...")
    
    # File extensions to process
    extensions = ['*.py', '*.md', '*.txt', '*.sh', '*.html', '*.ipynb']
    
    # Directories to exclude
    exclude_dirs = {'.venv', '.git', '__pycache__', 'node_modules'}
    
    # Replacement patterns
    replacements = [
        ('ChaosHunter', 'ChaosHunter'),
        ('ChaosHunterInput', 'ChaosHunterInput'),
        ('ChaosHunterOutput', 'ChaosHunterOutput'),
        ('chashunter', 'chashunter'),
        ('chaos-hunter', 'chaos-hunter'),
        ('CHAOSHUNTER_', 'CHAOSHUNTER_'),
        ('chaos_hunter', 'chaos_hunter'),
        ('add_chashunter_icon', 'add_chashunter_icon'),
        ('ADD_CHAOS_HUNTER_ICON', 'ADD_CHAOS_HUNTER_ICON'),
        ('init_chashunter', 'init_chashunter'),
    ]
    
    total_files = 0
    total_changes = 0
    
    # Find all files
    for ext in extensions:
        for file_path in glob.glob(f"**/{ext}", recursive=True):
            # Skip excluded directories
            if any(exclude_dir in file_path for exclude_dir in exclude_dirs):
                continue
                
            total_files += 1
            print(f"Processing: {file_path}")
            
            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                file_changes = 0
                
                # Apply replacements
                for old_pattern, new_pattern in replacements:
                    if old_pattern in content:
                        content = content.replace(old_pattern, new_pattern)
                        file_changes += content.count(new_pattern) - original_content.count(new_pattern)
                
                # Write back if changes were made
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"  Updated {file_changes} occurrences")
                    total_changes += file_changes
                else:
                    print("  No changes needed")
                    
            except Exception as e:
                print(f"  Error processing {file_path}: {e}")
    
    print(f"\nRename process completed!")
    print(f"Files processed: {total_files}")
    print(f"Total changes made: {total_changes}")
    print("\nNext steps:")
    print("1. Rename the chaos_hunter directory (if not already done)")
    print("2. Rename ChaosHunter_demo.py (if not already done)")
    print("3. Rename chaos_hunter/chaos_hunter.py to chaos_hunter.py")
    print("4. Test the application")

if __name__ == "__main__":
    rename_in_files()
