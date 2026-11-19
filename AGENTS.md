# FolioSentry — Agent Instructions

## 프로젝트 정체성
- 개인 1인 사용을 위한 국내·해외 주식/ETF 포트폴리오 모니터링 도구.
- 보유/관심 종목 등록, 시세·차트 분석, 종목 뉴스, 규칙 기반 신호, 알림 제공.
- **주문 자동 실행, 수익 보장, 공개 투자자문, 유료 사용자 기능은 범위 밖**.
- 기본 UI·설명·문서는 한국어. 코드 식별자·API 필드는 영어.

## 개발 우선순위
1. 사용자 정보·API 키·보유 자산 보호와 신뢰할 수 있는 데이터.
2. 재현 가능한 지표·신호 계산, 근거 표시, 장애 시 fail closed.
3. 최소 의존성, 작은 단위 구현, 테스트, 비용 절감.
4. AI는 뉴스 요약·설명만 담당. 최종 신호는 결정론적 규칙 엔진에서 생성.

## 아키텍처 원칙
- 모노레포: `backend/` (FastAPI + Python), `frontend/` (React + TypeScript), `docs/`.
- PostgreSQL, Docker Compose. 개인용 MVP는 별도 Redis/Kafka/마이크로서비스 금지.
- 시세/뉴스 공급자 의존성을 adapter/interface로 격리하고, 제한·재시도·캐시·중복 제거 적용.
- 국내/해외 시장을 모두 `exchange + symbol + currency`로 식별. 시간은 UTC 저장, 시장 타임존에서 일정 계산.
- 시세에는 시점, 출처, 조정 여부, 누락/지연 상태를 함께 보존.
- 신호에는 전략 버전, 지표 입력, 임계값, 근거, 계산 시점, 데이터 상태를 저장.
- 최신성/무결성 미확인 시 매수·매도 신호를 억제하고 오류 상태를 표시한다.
- 뉴스는 제목, 출처, 공개 시각, 원문 URL, 종목 관련성·중복 그룹을 중심으로 저장한다. 기사 무단 전문 수집 금지.
- 지표 계산 시 미래 데이터 참조(look-ahead) 금지. 백테스트에는 거래비용과 생존편향 등 제약 명시.

## 고정된 배포 및 LLM 정책 (2026-11-18)
- **최종 배포 대상은 사용자의 집에 있는 개인 MiniPC**다. 회사 GPU 서버/ModelOps 호스트에 FolioSentry 애플리케이션·DB·스케줄러를 배포하지 않는다.
- MiniPC는 Ubuntu 26.04 LTS/8 논리코어/14GiB RAM/39GB 여유 디스크, Docker 29.6.2 및 Compose 5.3.1임을 읽기 전용 사전 점검으로 확인. 18901·18902 포트 미점유. Traefik 상세 네트워크/entrypoint/resolver는 아직 미확인. 실제 환경 확인 전 포트 개방/배포 명령 실행 금지.
- 개인 MiniPC의 다른 서비스에 간섭하지 않도록 별도 Compose 프로젝트·볼륨·네트워크를 사용하고 자원 사용량/백업을 관리한다.
- **LLM은 선택 기능**이다. 종목 뉴스 요약·설명이 필요해질 때 기존 ModelOps Gateway API를 외부 서비스로 호출할 수 있게 adapter로 분리한다.
- MiniPC에 LLM 모델·GPU 런타임 설치를 기본 요구사항으로 추가하지 않는다. Gateway 미연결·장애 시에도 핵심 차트/규칙 신호/뉴스 원문 조회가 동작해야 한다.
- Gateway URL, 인증, 호출 가능한 모델, 접근 정책은 나중에 명시적으로 확인한다. 사용자 보유 수량·평균 단가·계좌 정보를 Gateway로 전송하지 않는다.
- 회사 운영 Gateway를 개인 목적으로 사용하는 경우 **사전 이용 허용 여부**, 원문/요약 데이터 전송과 감사 정책, 네트워크 접근 안전성을 확인해야 한다.
- 상세: `docs/DEPLOYMENT_TARGET.md`.

## 비밀정보·운영 안전
- 모든 토큰, API 키, 계좌 정보, DB 비밀번호는 환경변수/비밀 저장소에서만 로드.
- `.env`, 실계좌·보유내역·실시세 덤프, 로그 내 인증정보는 절대 커밋하지 않는다.
- 외부 API 권한은 조회(read-only) 최소 권한. 주문 API는 구현하지 않는다.
- 로컬 개발 데이터는 가상 종목/가상 보유 내역으로 테스트.
- 사용자의 승인 없이 배포, DB 초기화/삭제, 데이터 마이그레이션, 비밀정보 접근, PR 병합 금지.

## 작업 방법 (Cursor 토큰 최소화)
- 현재 작업 범위의 관련 파일과 이 문서만 읽고 시작한다. 전체 저장소 무차별 탐색 금지.
- ChatGPT에서 작성한 PRD/ARCHITECTURE/ROADMAP를 요구사항의 기준으로 삼는다.
- 작은 작업 한 개씩 구현하고, 범위 외 리팩터링·패키지 도입 금지.
- 구현 결과 보고: 변경 파일, 핵심 변경, 실행한 테스트 및 결과, 남은 위험/차단 사항만 짧게.
- 새로운 설계 결정은 `docs/ARCHITECTURE.md`에 기록하고 필요하면 이 파일도 갱신.
- 기존 운영 서비스나 로컬 컨테이너에 영향을 주지 않도록 이름, 포트, 볼륨, 네트워크를 격리한다.

## 검증 게이트
- Backend: 단위 테스트, 입력 검증, 타임존/휴장/결측 데이터 케이스.
- Frontend: typecheck, build, 핵심 상태 UI 테스트.
- 데이터·전략: 결정론적 fixture, 반복 실행 일치, 중복 신호 억제.
- 실 API 연결 전 반드시 샌드박스/모의 데이터 테스트.
- 장애/레이트리밋/오래된 시세에 대해 오탐 알림이 발생하지 않는지 확인.

관련 문서: `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/DATA_MODEL.md`, `docs/API_CONTRACT.md`, `docs/FIGMA_MAKE_BRIEF.md`.

## Phase 1A 디자인/계약 보호
- `docs/API_CONTRACT.md`에 **계획**된 엔드포인트는 별도 구현 PR 전까지 미구현으로 취급한다.
- `GET /api/v1/demo/overview`는 디자인 미리보기용 고정 허구 데이터다. 반드시 DEMO 표기, 실거래/실시세로 해석 금지.
- Figma Make 산출물의 화면 구조가 확정되기 전까지 Frontend를 임의로 재디자인하지 않는다.
- 금융 소수는 문자열 Decimal로 직렬화하고, 0과 NULL, STALE과 UNAVAILABLE을 구분한다.
- 설계·코드·마이그레이션을 분리하여 변경하며 기존 운영 DB를 자동 초기화/수정하지 않는다.

## AUTH-01 절대 준수사항 (2026-11-19)
- 실제 개인 보유 종목/수량/매수가 등록과 외부 네트워크 공개는 **로그인/세션/Backend API 차단 검증 이후**에만 허용.
- `/api/v1/*`는 로그인 API 하나를 제외하고 기본 거부. 새 API는 인증 미들웨어를 우회하지 않는다.
- 소유자 계정은 CLI로 단 한 번만 생성. 초기 비밀번호/비밀번호 재설정 링크/무인 가입 엔드포인트 작성 금지.
- Argon2id 해시, DB에는 세션 ID hash만 저장. HttpOnly + SameSite=Strict 쿠키 유지. 운영 Secure=true/HTTPS 필수.
- 모든 상태 변경은 정확한 Origin 허용목록 및 CSRF 헤더 검사. CORS 와일드카드, auth 우회 플래그, JWT localStorage 금지.
- HTTP 개발 쿠키는 loopback 전용이며 `ALLOW_HTTP_DEV=true`가 명시된 경우에만 예외 허용.
- `docs/AUTH_DESIGN.md`와 인증 관련 테스트를 변경 시 함께 갱신. 계정/세션/로그인 DB 마이그레이션을 무승인으로 실행 금지.
- 소유자 인증 DB 준비/세션 검증 실패 시 개인 데이터 응답 금지.

## UI-02 API 화면 계약 (2026-11-18)
- 유일한 시연용 데이터 원천은 `GET /api/v1/demo/overview`. `frontend/src/demoApi.ts`를 통하지 않는 프론트엔드 가짜 주가/뉴스/신호 배열을 새로 만들지 않는다.
- DEMO 모드 검증 실패, HTTP 오류/네트워크 오류 시 **실제 데이터인 듯한 대체 수치**로 fallback 하지 않는다.
- `UNAVAILABLE` 시세는 가격·평가손익을 빈 값으로 표시한다. 종목마다 서로 다른 `instrument.id`로 상세 연결한다.
- 금액, 수량, 퍼센트는 decimal string 계약을 보존한다. JS float로 잔고/손익 계산 금지.
- 미구현 OHLCV/지표·뉴스 기사·AI 요약·알림 발송은 **미지원/DEMO**로 표시. 실제 결과처럼 꾸미지 않는다.
- Phase 1 CRUD·외부 시세/뉴스·ModelOps Gateway·운영 배포는 UI-02 범위 밖. 실제 UI 적용 전 데스크톱/모바일 브라우저 확인.
- 상세 테스트와 수용 기준: `docs/UI02_DEMO_INTEGRATION.md`.

## AUTH-01 실제 브라우저 검증 게이트
- `AUTH-01 Browser Acceptance` GitHub Actions와 `frontend/e2e/auth-browser-smoke.mjs`를 유지한다.
- 테스트 환경은 일회용 PostgreSQL, 가상 소유자, DEMO 자산, 루프백 HTTP 예외만 사용. 가정 MiniPC/회사 서버/실 API에 테스트 접속 금지.
- 브라우저에서 미인증 요청, 로그인/로그아웃, 세션 복원, CSRF/Origin, API 장애 차단, 390px 모바일까지 확인.
- 한글 스크린샷 검사 시 CI에 한글 폰트를 제공한다. 테스트 러너의 글꼴 누락을 제품 데이터 문제로 오판하지 않는다.
- CI 통과는 운영 배포 승인이나 실제 HTTPS 접근성 검증을 대체하지 않는다.
- 관련 기록: `docs/AUTH_BROWSER_ACCEPTANCE.md`.

## AUTH-02 MiniPC 읽기 전용 사전 점검 (2026-11-19)
- 개인 MiniPC의 컨테이너/포트/자원 상태를 추정하지 않는다. `scripts/minipc-auth-preflight.sh` 결과를 먼저 확인한다.
- 사전 점검 스크립트는 Docker 생성·시작·재시작·중지·삭제, DB 연결/마이그레이션, `.env`나 토큰 열람을 수행하지 않는다.
- 기존 `folio-sentry`·homevoice 등 다른 Compose 프로젝트를 수정하지 않는다. 미리보기 설치를 승인받을 때도 독립 프로젝트/볼륨/네트워크와 loopback 바인딩을 먼저 검증한다.
- 실제 배포 전 사용자가 LAN/외부 접속 선호를 명시하지 않았다면 임의로 공개하지 않는다. HTTP 개발 쿠키는 루프백 전용, 외부 원격접속은 별도 HTTPS/VPN 설계 후.
- 안전 점검 완료 마커는 배포 승인이나 DB 마이그레이션 승인으로 취급하지 않는다.
- 계획/수행 경계: `docs/MINIPC_AUTH_PREVIEW_PLAN.md`. 

## DEPLOY-01 — 집 MiniPC 기존 Traefik/DuckDNS (2026-11-19)
- 실제 MiniPC에는 기존 Traefik, DuckDNS, ipTIME 포트포워딩이 있으며 `https://picknext.ramza.duckdns.org` 사용 중. 2026-11-19 확인한 라우팅 값은 **외부 Docker 네트워크 `proxy`, HTTPS entrypoint `websecure`, TLS resolver `myresolver`**. 이 라우터와 공유기 규칙을 **수정하지 않는다**.
- 배포 설계는 `compose.production.yml` + `compose.traefik.yml`, 정적 Nginx/Vite 빌드(`frontend/Dockerfile.prod`)로 분리. Backend·DB는 호스트 포트 노출 금지. frontend만 기존 Traefik 네트워크에 연결.
- `bash scripts/deploy.sh inspect`로 기존 Traefik 네트워크·entrypoint·resolver 단서를 민감정보 없이 확인, `configure`는 최초에만 개인 설정·암호를 생성, `check`는 배포 없이 검증.
- `db-init`은 **새 FolioSentry DB 생성/마이그레이션/개인 계정 초기화**, `publish`는 **공개 HTTPS 경로 활성화**라는 운영 변경이므로 각각 사용자 명시적 승인 전 실행하지 않는다. PR Draft 상태에서는 금지.
- `scripts/deploy.sh`는 검토된 `main`·깨끗한 워크트리·GitHub 동기화 상태를 실제 명령 실행의 필수조건으로 검증해야 한다.
- 운영 DB 비밀번호를 `.env.deploy`에 담지 않고 사용자의 `~/.config/folio-sentry/pg_password`(권한 600) Docker Secret 파일로 보관. 로그인 비밀번호는 별도 대화형 생성. 모든 값과 토큰은 Git에 기록하지 않는다.
- DuckDNS 하위 호스트 레코드가 기존 IP를 가리키더라도 새 HTTPS 인증서 존재/유효성은 별도 검증해야 한다. 장기 개인 정보 저장 전 외부 VPN/추가 2차인증과 백업·복구 검증.
- 전용 배포 절차: `docs/TRAEFIK_MINIPC_DEPLOYMENT.md`.

- 후보 URL `foliosentry.ramza.duckdns.org`는 DNS 조회/인증서 발급이 실제 확인되기 전까지 **확정 주소가 아니다**. 공개 HTTPS 배포를 승인했다고 해석하지 않는다.
- `scripts/check-duckdns-route.sh`는 기존 `picknext.ramza.duckdns.org`와 새 후보 주소의 DNS IPv4 응답만 비교하고 실제 공인 IP는 출력하지 않는다. MiniPC에서 2026-11-19 IPv4 매핑 **일치 확인 완료**. DNS 일치는 TLS·접근 제어·운영 승인과 동일하지 않다.
- `scripts/check-existing-tls.py`는 기존 PickNext 도메인에 대한 인증서 신뢰와 SAN 커버리지 확인만 수행한다. **새 FolioSentry TLS 인증서 검증 완료로 오인하지 않는다.** 운영 변경·비밀 정보 접근 금지.
- `scripts/deploy.sh configure`는 MiniPC에서 확인된 세 Traefik 이름을 Enter 기본값으로 제안하되, 실제 사용자는 도메인·네트워크 구성 변경 시 값을 검증한다.
