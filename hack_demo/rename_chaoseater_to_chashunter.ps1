# PowerShell script to rename ChaosEater to ChaosHunter
# Run this script from the project root directory

Write-Host "Starting ChaosEater to ChaosHunter rename process..." -ForegroundColor Green

# Get all Python files recursively
$pythonFiles = Get-ChildItem -Path . -Recurse -Include "*.py", "*.md", "*.txt", "*.sh", "*.html", "*.ipynb" | Where-Object { $_.FullName -notlike "*\.venv\*" -and $_.FullName -notlike "*\.git\*" -and $_.FullName -notlike "*\__pycache__\*" }

Write-Host "Found $($pythonFiles.Count) files to process" -ForegroundColor Yellow

$totalChanges = 0

foreach ($file in $pythonFiles) {
    Write-Host "Processing: $($file.Name)" -ForegroundColor Cyan
    
    # Read file content
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    $originalContent = $content
    
    # Perform replacements
    $content = $content -replace "ChaosEater", "ChaosHunter"
    $content = $content -replace "ChaosEaterInput", "ChaosHunterInput"
    $content = $content -replace "ChaosEaterOutput", "ChaosHunterOutput"
    $content = $content -replace "chaoseater", "chashunter"
    $content = $content -replace "chaos-eater", "chaos-hunter"
    $content = $content -replace "CHAOSEATER_", "CHAOSHUNTER_"
    $content = $content -replace "chaos_eater", "chaos_hunter"
    $content = $content -replace "add_chaoseater_icon", "add_chashunter_icon"
    $content = $content -replace "ADD_CHAOS_EATER_ICON", "ADD_CHAOS_HUNTER_ICON"
    $content = $content -replace "init_choaseater", "init_chashunter"
    
    # Check if content changed
    if ($content -ne $originalContent) {
        # Write back to file
        Set-Content -Path $file.FullName -Value $content -Encoding UTF8
        $changes = ([regex]::Matches($originalContent, "ChaosEater|chaoseater|CHAOSEATER|chaos-eater|chaos_eater")).Count
        $totalChanges += $changes
        Write-Host "  Updated $changes occurrences" -ForegroundColor Green
    } else {
        Write-Host "  No changes needed" -ForegroundColor Gray
    }
}

Write-Host "`nRename process completed!" -ForegroundColor Green
Write-Host "Total changes made: $totalChanges" -ForegroundColor Yellow
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Rename the chaos_hunter directory (if not already done)"
Write-Host "2. Rename ChaosHunter_demo.py (if not already done)"
Write-Host "3. Rename chaos_hunter/chaos_eater.py to chaos_hunter.py"
Write-Host "4. Test the application"
