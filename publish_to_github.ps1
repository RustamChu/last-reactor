# ============================================================
#  ПОСЛЕДНИЙ РЕАКТОР - выложить проект на GitHub одним кликом
#  ПКМ по этому файлу -> "Выполнить с помощью PowerShell"
#
#  Скрипт сам: поставит git (если его нет), создаст репозиторий,
#  сделает коммит и запушит. Повторный запуск просто зальёт
#  свежие изменения.
# ============================================================
$ErrorActionPreference = "Continue"
trap {
    Write-Host ""
    Write-Host ("  Ошибка: " + $_.Exception.Message) -ForegroundColor Red
    Read-Host "Нажмите Enter, чтобы закрыть"
    exit 1
}
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

# --- защита от запуска "копипастой" ---------------------------------------
# Если содержимое файла просто вставили в консоль, $PSScriptRoot пуст, и
# скрипт создал бы репозиторий в текущей папке (например, в C:\Users\Имя).
if ([string]::IsNullOrEmpty($PSScriptRoot)) {
    Write-Host ""
    Write-Host "  Скрипт нужно ЗАПУСКАТЬ файлом, а не вставлять текст в консоль." -ForegroundColor Red
    Write-Host "  Иначе git-репозиторий создастся не в папке игры, а там, где вы сейчас." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Правильно: ПКМ по publish_to_github.ps1 -> Выполнить с помощью PowerShell" -ForegroundColor Yellow
    Write-Host "  Или командой:" -ForegroundColor Yellow
    Write-Host '  powershell -ExecutionPolicy Bypass -File "<путь>\neon-doom\publish_to_github.ps1"' -ForegroundColor Yellow
    Write-Host ""
    return
}

Set-Location -Path $PSScriptRoot

# страховка: работаем только там, где лежит сама игра
if (-not (Test-Path (Join-Path $PSScriptRoot "main.py"))) {
    Write-Host "  Рядом со скриптом нет main.py - похоже, это не папка игры. Останавливаюсь." -ForegroundColor Red
    Read-Host "Нажмите Enter, чтобы закрыть"
    exit 1
}

# --- настройки -------------------------------------------------------------
$GitHubUser = "RustamChu"
$RepoName   = "last-reactor"
$RepoDesc   = "Tower defense in pure Python + pygame: flow-field pathfinding, target interception, zero assets"

$RemoteUrl  = "https://github.com/$GitHubUser/$RepoName.git"
$PageUrl    = "https://github.com/$GitHubUser/$RepoName"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "    $msg" -ForegroundColor Red }
function Pause-Exit($code) {
    Write-Host ""
    Read-Host "Нажмите Enter, чтобы закрыть"
    exit $code
}

Write-Host ""
Write-Host "  Публикация ПОСЛЕДНИЙ РЕАКТОР -> $PageUrl" -ForegroundColor Magenta
Write-Host ""

# --- 1. git на месте? ------------------------------------------------------
Write-Step "Проверяю git..."
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "git не найден."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Step "Ставлю git через winget..."
        winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements
        Write-Ok "Готово. Закройте это окно и запустите скрипт ещё раз."
    } else {
        Write-Err "Скачайте git вручную, потом запустите скрипт заново."
        Start-Process "https://git-scm.com/download/win"
    }
    Pause-Exit 1
}
Write-Ok (git --version)

# --- 2. кто коммитит -------------------------------------------------------
if (-not (git config user.name)) {
    git config --global user.name $GitHubUser
    Write-Ok "Прописал имя коммитера: $GitHubUser"
}
if (-not (git config user.email)) {
    git config --global user.email "$GitHubUser@users.noreply.github.com"
    Write-Ok "Прописал почту коммитера (скрытая, реальную git не узнает)"
}

# --- 3. репозиторий и коммит ----------------------------------------------
if (-not (Test-Path ".git")) {
    Write-Step "Создаю локальный репозиторий..."
    git init | Out-Null
    git branch -M main
    Write-Ok "Ветка main готова"
}

git add -A
if (git status --porcelain) {
    $msg = Read-Host "Сообщение коммита (Enter - оставить стандартное)"
    if ([string]::IsNullOrWhiteSpace($msg)) { $msg = "THE LAST REACTOR: tower defense" }
    git commit -m $msg | Out-Null
    Write-Ok "Коммит сделан"
} else {
    Write-Ok "Новых изменений нет"
}

$null = & git log -1 --oneline 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Err "Нечего пушить - в репозитории нет ни одного коммита."
    Pause-Exit 1
}

# --- 4. remote -------------------------------------------------------------
$hasRemote = (git remote) -contains "origin"
if ($hasRemote) {
    $current = (git remote get-url origin).Trim()
    if ($current -ne $RemoteUrl) {
        Write-Warn "origin смотрел на $current - переставляю на ваш репозиторий"
        git remote set-url origin $RemoteUrl
    }
}

# --- 5. публикуем ----------------------------------------------------------
$useGh = $false   # gh отключён (publish_all_no_gh.ps1)

if ($useGh) {
    Write-Step "Нашёл GitHub CLI - делаю всё автоматически"
    $null = & gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Step "Нужно войти в GitHub, сейчас откроется браузер..."
        gh auth login --hostname github.com --web
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Войти не получилось."
            Pause-Exit 1
        }
    }

    $null = & gh repo view "$GitHubUser/$RepoName" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Step "Создаю репозиторий и заливаю код..."
        if (-not $hasRemote) {
            gh repo create "$GitHubUser/$RepoName" --public --source . --remote origin --push --description $RepoDesc
        } else {
            gh repo create "$GitHubUser/$RepoName" --public --description $RepoDesc
            git push -u origin main
        }
    } else {
        Write-Step "Репозиторий уже есть - заливаю изменения..."
        if (-not $hasRemote) { git remote add origin $RemoteUrl }
        git push -u origin main
    }
} else {
    Write-Step "GitHub CLI не установлен - публикую обычным git"
    if (-not $hasRemote) {
        Write-Host ""
        Write-Warn "Сейчас откроется страница создания репозитория."
        Write-Warn "Имя: $RepoName, тип Public, галочки README / .gitignore / license НЕ ставьте."
        Write-Warn "Нажмите Create repository и вернитесь сюда."
        Write-Host ""
        Start-Process "https://github.com/new?name=$RepoName&visibility=public"
        Read-Host "Нажмите Enter, когда репозиторий создан"
        git remote add origin $RemoteUrl
    }
    Write-Step "Пушу (Windows может попросить войти в GitHub)..."
    git push -u origin main
}

# --- 6. если удалённый репозиторий не пустой ------------------------------
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Пуш отклонён - похоже, на GitHub уже что-то лежит."
    $answer = Read-Host "Подтянуть то, что там есть, и попробовать снова? (y/n)"
    if ($answer -eq "y") {
        git pull --rebase origin main
        git push -u origin main
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Не получилось. Посмотрите сообщение git выше."
        Pause-Exit 1
    }
}

Write-Host ""
Write-Ok "Готово! Проект здесь: $PageUrl"
Start-Process $PageUrl
Pause-Exit 0
