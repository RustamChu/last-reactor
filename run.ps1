# ============================================================
#  ПОСЛЕДНИЙ РЕАКТОР - запуск одним кликом
#  Дважды кликните PLAY.bat, либо ПКМ по этому файлу ->
#  "Выполнить с помощью PowerShell".
#
#  Скрипт сам найдёт Python, поставит pygame и запустит игру.
# ============================================================
$ErrorActionPreference = "Stop"
# в PowerShell 7.3+ вывод в stderr от внешних программ иначе может стать ошибкой
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

# скрипт нужно запускать файлом, а не вставлять его текст в консоль
if ([string]::IsNullOrEmpty($PSScriptRoot)) {
    Write-Host ""
    Write-Host "  Запускайте файлом: ПКМ по run.ps1 -> Выполнить с помощью PowerShell" -ForegroundColor Red
    Write-Host "  (или просто дважды кликните PLAY.bat)" -ForegroundColor Yellow
    Write-Host ""
    return
}

Set-Location -Path $PSScriptRoot

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "    $msg" -ForegroundColor Red }
function Pause-Exit($code) {
    Write-Host ""
    Read-Host "Нажмите Enter, чтобы закрыть"
    exit $code
}

Write-Host ""
Write-Host "  A S H E N   D E P T H S" -ForegroundColor Magenta
Write-Host ""

# --- 1. ищем рабочий Python 3 --------------------------------------------
Write-Step "Ищу Python 3..."
$exe = $null
$extra = @()
foreach ($candidate in @(@("py", "-3"), @("python"), @("python3"))) {
    $name = $candidate[0]
    $pyArgs = @()
    if ($candidate.Count -gt 1) { $pyArgs = $candidate[1..($candidate.Count - 1)] }
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { continue }
    try {
        $ver = & $name @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 8) {
            $exe = $name
            $extra = $pyArgs
            Write-Ok "Python $ver ($name)"
            break
        }
    } catch { }
}

# --- 2. если Python нет - ставим ------------------------------------------
if (-not $exe) {
    Write-Err "Python 3.8+ не найден."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Step "Ставлю Python через winget..."
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        Write-Ok "Готово. Закройте это окно и запустите игру ещё раз."
    } else {
        Write-Err "Скачайте Python вручную и отметьте галочку 'Add Python to PATH'."
        Start-Process "https://www.python.org/downloads/"
    }
    Pause-Exit 1
}

# --- 3. проверяем и при необходимости ставим pygame -----------------------
Write-Step "Проверяю pygame..."
& $exe @extra -c "import pygame" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Step "Ставлю pygame (один раз, ~10 МБ)..."
    & $exe @extra -m pip install --user --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Step "Не вышло, пробую сборку pygame-ce..."
        & $exe @extra -m pip install --user --disable-pip-version-check pygame-ce
    }
    & $exe @extra -c "import pygame" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "pygame поставить не удалось. Проверьте интернет и попробуйте ещё раз."
        Pause-Exit 1
    }
}
Write-Ok "pygame на месте"

# --- 4. поехали ------------------------------------------------------------
Write-Step "Запускаю. Приятной игры!"
Write-Host ""
& $exe @extra main.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Err "Игра завершилась с ошибкой (код $LASTEXITCODE). Текст ошибки выше."
    Pause-Exit $LASTEXITCODE
}
