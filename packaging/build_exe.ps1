# Build dist\BeamForge.exe, a single-file Windows application.
#
# Usage, from the repository root, with the gui and build extras installed:
#     pip install -e ".[gui,build]"
#     powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
#
# -Python   Python interpreter to use (default: the one on PATH).
# -WorkDir  Folder for temporary build files (default: build\).

param(
    [string]$Python = "python",
    [string]$WorkDir = "build"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force $WorkDir | Out-Null
$icon = Join-Path (Resolve-Path $WorkDir) "beamforge.ico"

$env:PYTHONPATH = Join-Path $root "src"
& $Python packaging\make_icon.py $icon
if ($LASTEXITCODE -ne 0) { throw "icon generation failed" }
# Still picture shown while the exe unpacks; the animated screen takes over after.
# It needs the system fonts, so Qt must not run in "offscreen" mode here.
$splash = Join-Path (Resolve-Path $WorkDir) "beamforge_splash.png"
& $Python packaging\make_splash.py $splash
if ($LASTEXITCODE -ne 0) { throw "start-up picture generation failed" }

# Qt modules the application does not use; leaving them out keeps the file small.
$exclude = @(
    "matplotlib", "IPython", "pytest",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.Qt3DCore",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtLocation",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtWebSockets", "PySide6.QtDesigner"
)
$excludeArgs = $exclude | ForEach-Object { "--exclude-module"; $_ }

& $Python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name BeamForge --icon $icon --splash $splash --paths src `
    --distpath dist --workpath $WorkDir --specpath $WorkDir `
    @excludeArgs packaging\beamforge_gui.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host "Built $(Join-Path $root 'dist\BeamForge.exe')"
