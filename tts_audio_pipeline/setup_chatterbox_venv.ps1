# Chatterbox 로컬용 가상환경 (Python 3.12 / 3.11 / 3.10 우선)
# 3.14 등 최신 버전은 spacy-pkuseg 등에서 wheel이 없어 소스 빌드 → MSVC 필요로 실패하기 쉽습니다.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvDir = Join-Path $PSScriptRoot ".venv_chatterbox"
$pyexe = $null
foreach ($ver in @("3.12", "3.11", "3.10")) {
    try {
        $c = & py "-$ver" -c "import sys; print(sys.executable)" 2>$null
        if ($c -and (Test-Path $c.Trim())) {
            $pyexe = $c.Trim()
            Write-Host "사용할 Python: $pyexe (py -$ver)"
            break
        }
    } catch { }
}
if (-not $pyexe) {
    Write-Error @"
Python 3.12·3.11·3.10 을 찾지 못했습니다. python.org 에서 3.12 64비트를 설치한 뒤
Windows에서 'py' 런처가 인식되는지 확인하세요. 그 다음 이 스크립트를 다시 실행하세요.
"@
    exit 1
}

if (Test-Path $venvDir) {
    Write-Host "기존 가상환경 삭제: $venvDir"
    Remove-Item -Recurse -Force $venvDir
}
& $pyexe -m venv $venvDir
$pip = Join-Path $venvDir "Scripts\pip.exe"
$python = Join-Path $venvDir "Scripts\python.exe"

& $python -m pip install -U pip wheel
Write-Host ""
Write-Host "PyTorch는 GPU/CPU에 맞게 https://pytorch.org 안내를 따른 뒤, 이 venv에 설치하는 것을 권장합니다."
Write-Host "예(CPU만): pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu"
Write-Host ""
& $pip install -r (Join-Path $PSScriptRoot "requirements-chatterbox.txt")
& $pip install -r (Join-Path $PSScriptRoot "requirements.txt")

Write-Host ""
Write-Host "Done. Run GUI from this folder (so txt2audio package is found):"
Write-Host "  cd `"$PSScriptRoot`""
Write-Host "  & `"$python`" -m txt2audio --gui"
