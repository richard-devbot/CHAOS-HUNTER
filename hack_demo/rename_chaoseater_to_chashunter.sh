#!/bin/bash

echo "Starting ChaosHunter to ChaosHunter rename process..."

# Find all relevant files and perform replacements
find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/ChaosHunter/ChaosHunter/g' {} \;

find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/ChaosHunterInput/ChaosHunterInput/g' {} \;

find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/ChaosHunterOutput/ChaosHunterOutput/g' {} \;

find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/chashunter/chashunter/g' {} \;

find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/chaos-hunter/chaos-hunter/g' {} \;

find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/CHAOSHUNTER_/CHAOSHUNTER_/g' {} \;

find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/chaos_hunter/chaos_hunter/g' {} \;

find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/add_chashunter_icon/add_chashunter_icon/g' {} \;

find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/ADD_CHAOS_HUNTER_ICON/ADD_CHAOS_HUNTER_ICON/g' {} \;

find . -type f \( -name "*.py" -o -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.html" -o -name "*.ipynb" \) \
    -not -path "./.venv/*" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -exec sed -i 's/init_chashunter/init_chashunter/g' {} \;

echo "Rename process completed!"
echo "Next steps:"
echo "1. Rename the chaos_hunter directory (if not already done)"
echo "2. Rename ChaosHunter_demo.py (if not already done)"
echo "3. Rename chaos_hunter/chaos_hunter.py to chaos_hunter.py"
echo "4. Test the application"
