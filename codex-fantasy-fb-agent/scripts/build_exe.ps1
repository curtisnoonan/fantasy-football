param(
    [switch]$Clean
)

Write-Host "Building Draft Salary Cap Editor (Windows EXE)" -ForegroundColor Cyan

if ($Clean) {
    Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue | Out-Null
}

python -m pip install --upgrade pip --disable-pip-version-check
python -m pip install pyinstaller

$argsList = @("--noconsole", "--onefile", "--name", "DraftSalaryCapEditor")
if (Test-Path -Path "data/initial_roster.csv") {
    # On Windows, use semicolon in --add-data
    $argsList += @("--add-data", "data\initial_roster.csv;data")
}
$argsList += "draft_cap_gui.py"

python -m PyInstaller @argsList

Write-Host "Done. Binary at: dist/DraftSalaryCapEditor.exe" -ForegroundColor Green
