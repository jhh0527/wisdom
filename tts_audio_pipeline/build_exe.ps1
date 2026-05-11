# UTF-8 TTS -> txt2audio.exe / txt2audio_gui.exe 빌드 (PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

foreach ($d in @("build", "dist")) {
    $p = Join-Path $PSScriptRoot $d
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}

function Get-PythonExe {
    $candidates = @()
    try {
        $p = & py -3 -c "import sys; print(sys.executable)" 2>$null
        if ($p) { $candidates += $p.Trim() }
    } catch { }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { $candidates += $py.Source }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    $root = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $root) {
        Get-ChildItem $root -Directory "Python3*" -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object {
                $exe = Join-Path $_.FullName "python.exe"
                if (Test-Path $exe) { $exe }
            } | Select-Object -First 1 | ForEach-Object { return $_ }
    }
    return $null
}

$pyexe = Get-PythonExe
if (-not $pyexe) {
    Write-Error "Python을 찾을 수 없습니다. python.org 3.9+ 설치 또는 PATH에 python을 추가하세요."
    exit 1
}

Write-Host "Python: $pyexe"
& $pyexe --version

& $pyexe -m pip install -q -r (Join-Path $PSScriptRoot "requirements.txt")
& $pyexe -m pip install -q -r (Join-Path $PSScriptRoot "requirements-build.txt")
& $pyexe -m PyInstaller --clean --noconfirm (Join-Path $PSScriptRoot "txt2audio.spec")
& $pyexe -m PyInstaller --clean --noconfirm (Join-Path $PSScriptRoot "txt2audio_gui.spec")

Write-Host ""
Write-Host "완료:"
Write-Host "  CLI  $(Join-Path $PSScriptRoot 'dist\txt2audio.exe')"
Write-Host "  GUI  $(Join-Path $PSScriptRoot 'dist\txt2audio_gui.exe')"
