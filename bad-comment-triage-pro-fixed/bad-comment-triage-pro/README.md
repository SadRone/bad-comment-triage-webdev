# Public Comment Triage Pro v2

실사용에 가까운 구조로 다시 설계한 공개 악성 댓글 수집 및 검토 우선순위 분류 프로젝트입니다.

> 이 프로그램은 법률 판단기가 아닙니다. `검토 우선`, `맥락 필요`, `낮은 우선순위`는 증거 정리와 전문가 검토를 돕는 triage 결과입니다. 공개적으로 접근 가능한 자료만 다루며 로그인 우회, 비공개 자료 접근, 작성자 신원 추적 기능은 포함하지 않습니다.

## 왜 V1과 다른가

V1은 검색 결과를 바로 긁은 뒤 조건에 맞지 않으면 조용히 버리는 구조라 0건이 나왔을 때 원인을 알기 어려웠습니다. V2는 수집과 분석을 분리하고 각 단계의 통계를 저장합니다.

```text
Browser
  │
  ▼
FastAPI API ───────────── PostgreSQL
  │                           ▲
  │ enqueue                   │ evidence / job / diagnostics
  ▼                           │
Redis ─────► Celery worker ───┘
                 │
       ┌─────────┼──────────┐
       ▼         ▼          ▼
   YouTube    Brave      Google CSE
     API      Search         API
       │         │          │
       └──── collection ────┘
                 │
          normalize/dedup
                 │
          transparent triage
                 │
          score + reasons
```

## 핵심 개선

- **수집기 플러그인 구조**: YouTube, Brave Search, Google Programmable Search를 독립 모듈로 분리했습니다.
- **공식 API 우선**: YouTube 댓글은 YouTube Data API v3를 사용합니다.
- **웹 보강 수집**: 검색 API가 찾은 공개 페이지는 `robots.txt`가 허용할 때만 제한적으로 본문을 읽습니다.
- **SSRF 방어**: 공개 페이지 보강 수집 시 localhost, 사설 IP, link-local 등은 차단합니다.
- **비동기 처리**: Celery + Redis로 검색 작업이 브라우저 요청과 분리됩니다.
- **영속 저장**: PostgreSQL에 작업, 결과, 진단 통계를 저장합니다.
- **중복 제거**: 정규화한 문장 SHA-256 hash로 동일 문장 중복을 제거합니다.
- **검색어 자동 확장**: 추가 키워드를 비워도 기본 악성 표현 검색어 조합을 생성합니다.
- **문맥 기반 대상 특정**: YouTube 댓글 자체에 이름이 없어도 영상 제목이 대상을 특정하면 문맥 신호로 처리합니다.
- **0건 원인 표시**: 검색 결과 수, 페이지 시도 수, robots 차단, HTTP 실패, 저장 수, 중복 수, API 오류가 UI에 표시됩니다.
- **투명한 분류**: 블랙박스 법률 판단 대신 감지된 신호와 점수 이유를 보여줍니다.
- **CSV export**: 원문 URL, 작성자 표시명, 날짜, 문장, 문맥, 점수와 이유를 내보냅니다.
- **API key 비노출**: key는 `.env`와 서버 컨테이너에만 존재하며 브라우저로 전송되지 않습니다.

## 폴더 구조

```text
bad-comment-triage-pro/
├─ docker-compose.yml
├─ .env.example
├─ README.md
├─ backend/
│  ├─ Dockerfile
│  ├─ requirements.txt
│  ├─ tests/
│  └─ app/
│     ├─ api/routes.py
│     ├─ analysis/rules.py
│     ├─ collectors/
│     │  ├─ base.py
│     │  ├─ youtube.py
│     │  ├─ brave.py
│     │  ├─ google_cse.py
│     │  └─ web_fetch.py
│     ├─ services/
│     │  ├─ query_expander.py
│     │  └─ orchestrator.py
│     ├─ core/config.py
│     ├─ db.py
│     ├─ models.py
│     ├─ worker.py
│     └─ main.py
└─ frontend/
   ├─ index.html
   ├─ styles.css
   └─ app.js
```

## Windows에서 실행

### 1. 압축 해제 후 폴더로 이동

```powershell
cd "$HOME\Desktop\bad-comment-triage-pro"
```

압축을 풀었을 때 폴더가 한 번 더 중첩되었다면 실제 `docker-compose.yml`이 있는 폴더까지 이동하십시오.

### 2. `.env` 생성

```powershell
Copy-Item .env.example .env
notepad .env
```

최소 하나의 수집기 API key가 필요합니다.

```env
YOUTUBE_API_KEY=본인키
BRAVE_SEARCH_API_KEY=
GOOGLE_CSE_API_KEY=
GOOGLE_CSE_CX=
```

YouTube만 설정해도 YouTube 댓글 수집은 작동합니다. 공개 웹 검색을 하려면 Brave 또는 Google CSE 중 하나를 추가하십시오.

### 3. Docker Desktop 실행

Docker Desktop에서 Engine이 running 상태인지 확인합니다.

```powershell
docker info
```

`Server:` 정보가 나오면 정상입니다.

### 4. 서비스 시작

```powershell
docker compose up --build
```

브라우저:

```text
http://localhost:8000
```

상태 API:

```text
http://localhost:8000/api/health
http://localhost:8000/api/providers
```

### 5. key가 실제 컨테이너에 전달됐는지 확인

```powershell
docker compose exec web printenv YOUTUBE_API_KEY
docker compose exec worker printenv YOUTUBE_API_KEY
```

키가 터미널에 보이므로 화면 공유 중이라면 이 명령은 사용하지 않는 편이 좋습니다.

## 추천 테스트

YouTube key만 설정한 상태라면 이름이 알려진 공개 인물을 대상에 입력하고 YouTube 수집기를 선택한 뒤 실행합니다. 추가 키워드는 처음에는 비워두는 것을 권장합니다. V2는 관련 영상을 먼저 찾고, 해당 영상의 댓글을 가져오기 때문에 댓글에 대상 이름이 반복되지 않아도 영상 제목을 문맥으로 활용합니다.

UI 상단의 `수집기 상태`가 `READY`인지 먼저 확인하십시오. `NOT CONFIGURED`라면 그 수집기는 실행되지 않습니다.

## 진단 통계 읽는 법

YouTube 예시:

```text
queries: 1
videos_found: 20
videos_scanned: 12
comment_pages: 24
comments_seen: 1840
replies_seen: 71
candidates: 200
saved: 176
duplicates: 24
```

웹 검색 예시:

```text
queries: 12
search_results: 120
snippets_kept: 18
pages_attempted: 45
robots_blocked: 13
http_failed: 5
candidates: 52
saved: 31
duplicates: 7
```

이 구조에서는 결과가 0이어도 `검색 API가 0건을 반환했는지`, `robots.txt 때문에 페이지를 읽지 못했는지`, `API 오류인지`, `후보는 있었지만 relevance filter에서 제외됐는지`를 구분할 수 있습니다.

## 분류 로직

현재 기본 분석기는 `rules-v2.0`입니다. 다음 신호를 개별적으로 기록합니다.

- 대상 직접 특정 또는 게시물 문맥을 통한 대상 특정
- 강한 모욕 표현
- 일반적 부정·모욕 표현
- 위협 또는 위해 암시
- 범죄·불법행위 사실 적시형 주장
- 주소·전화번호 등 개인정보 노출 신호
- 성적 비하 표현
- 추측·전언 표현
- 의견·취향 표현

점수는 **법적 승소 가능성이나 고소 가능성의 확률이 아닙니다.** 검토 순서를 정하기 위한 내부 우선순위입니다.

## 테스트

컨테이너가 올라간 상태에서:

```powershell
docker compose exec web pytest -q
```

또는 build 중 코드 문제가 의심되면:

```powershell
docker compose logs -f web
docker compose logs -f worker
```

## GitHub에 올릴 때

`.env`는 `.gitignore`에 포함되어 있습니다. **API key가 들어간 `.env`를 GitHub에 올리지 마십시오.**

```powershell
git init
git add .
git commit -m "Build production-style public comment triage pipeline"
git branch -M main
git remote add origin https://github.com/본인아이디/bad-comment-triage-pro.git
git push -u origin main
```

## 데이터와 운영상 주의

1. "인터넷의 모든 악플"을 완전히 수집하는 것은 기술적으로 보장할 수 없습니다. 검색 색인, 플랫폼 API 범위, 삭제 여부, 로그인 필요 여부, rate limit에 따라 coverage가 달라집니다.
2. 이 프로젝트는 공개 소스만 대상으로 합니다. 접근 제한 우회나 비공개 계정 수집은 의도적으로 구현하지 않았습니다.
3. 작성자 표시명은 증거 정리용으로만 저장합니다. 실명 추정, 신상 추적, 위치 추정 기능은 없습니다.
4. 실제 법적 검토에서는 원문 전체 맥락, 게시 시각, 공개성, 대상 특정성, 사실과 의견의 구분, 진실성 및 공익성 등 추가 요소가 필요할 수 있습니다.
5. 플랫폼 약관과 API 정책, 검색 API의 quota를 확인하여 운영하십시오.

## 다음 확장 포인트

`collectors/base.py`의 `EvidenceCandidate`와 `CollectorResult` 계약을 지키면 새 플랫폼을 독립적으로 추가할 수 있습니다. 예를 들어 향후 별도의 공식 API가 허용하는 범위에서 Reddit, X, 커뮤니티 검색 provider를 추가할 수 있습니다.

대규모 운영 시에는 PostgreSQL migration(Alembic), object storage 기반 원문 스냅샷, 사용자 인증, rate limiting, 감사 로그, queue autoscaling, structured logging, metrics, 법률가 검토 workflow를 추가하는 것이 좋습니다.
