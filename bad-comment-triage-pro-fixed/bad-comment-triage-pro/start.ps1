$ErrorActionPreference = 'Stop'

Write-Host "[1/4] Docker 확인" -ForegroundColor Cyan
try {
    docker info *> $null
} catch {
    Write-Host "Docker Engine에 연결할 수 없습니다. Docker Desktop을 실행한 뒤 다시 시도하세요." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host ".env를 생성했습니다." -ForegroundColor Yellow
}

$envText = Get-Content '.env' -Raw
$hasProvider = ($envText -match 'YOUTUBE_API_KEY=.+') -or ($envText -match 'BRAVE_SEARCH_API_KEY=.+') -or (($envText -match 'GOOGLE_CSE_API_KEY=.+') -and ($envText -match 'GOOGLE_CSE_CX=.+' ))
if (-not $hasProvider) {
    Write-Host "[2/4] 수집 API key가 아직 없습니다." -ForegroundColor Yellow
    Write-Host "메모장에서 .env가 열립니다. 최소 YOUTUBE_API_KEY 또는 Brave/Google CSE 설정을 입력하고 저장하세요." -ForegroundColor Yellow
    notepad .env
    Read-Host "저장한 뒤 Enter를 누르세요"
}

Write-Host "[3/4] 컨테이너 빌드 및 시작" -ForegroundColor Cyan
docker compose up -d --build

Write-Host "[4/4] 상태 확인" -ForegroundColor Cyan
Start-Sleep -Seconds 3
docker compose ps
Write-Host "브라우저에서 http://localhost:8000 을 여세요." -ForegroundColor Green
