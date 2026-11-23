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
- 소유자 계정은 CLI로 단 한 번만 생성. **비밀번호 허용 길이 8~128자(사용자 요청 2026-11-19)**. Argon2id 해시, 5회 로그인 실패/15분 잠금, CSRF·Origin 검사, Secure 쿠키 규칙 유지. 초기 비밀번호/비밀번호 재설정 링크/무인 가입 엔드포인트 작성 금지.
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

## DEPLOY-01 기존 TLS 인증서 검사 결과 (2026-11-19)
- PickNext TLS 인증서 신뢰·호스트 확인 PASS, 잔여 기간 31일, FolioSentry 후보 주소 SAN 포함 **NO**.
- `myresolver` 신규 인증서 발급은 아직 확인되지 않았다. 도메인 DNS 일치나 기존 PickNext 인증서 정상만으로 새 호스트 운영 HTTPS 준비 완료를 선언하지 않는다.
- `scripts/inspect-traefik-acme.py`는 기존 Traefik Docker 메타데이터에서 ACME challenge 방식·호스트 포트 매핑 힌트만 읽고 환경/인증서/설정파일/비밀키를 읽거나 출력하지 않는다.
- HTTP-01은 외부 80, TLS-ALPN-01은 외부 443 도달 및 발급 검증이 필요하다. Docker 포트 공개와 공유기·공인인터넷 도달성은 별개다.
- 실제 Router 공개와 인증서 발급은 별도 명시적 승인 및 운영 전 보안 점검 이후 수행.

## DEPLOY-01 TLS-ALPN 실측 및 사전 게이트 (2026-11-19)
- MiniPC의 기존 Traefik `myresolver`는 `TLS_ALPN_01`, Docker 443 publish, 인증서 저장소 bind/volume mount 확인. 이 사실은 외부 인터넷의 포트 도달, 인증서 발급 성공, 저장소 백업을 **의미하지 않는다**.
- `scripts/deploy.sh check`는 실행 전에 관측된 ACME 설정/443 바인딩/영속 마운트 및 새 DuckDNS 매핑을 검증하여 조건이 바뀌면 fail closed 한다.
- 공개 라우터가 실제 생성되기 전 신규 도메인 인증서 발급 PASS 주장 금지. 공개 전 사용자의 명시적 승인 및 기존 다른 서비스 영향 방지.

## DEPLOY-02 승인 후 공개 가드 (2026-11-19)
- FolioSentry 전용 DB는 초기화되었고 `auth_owner=1`, 운영 비밀번호 최소 길이 8자 정책. 공개 전에 다른 앱이나 DB를 변경/마이그레이션하면 안 된다.
- `scripts/deploy.sh publish`는 사전 점검, 준비된 소유자 계정, `scripts/backup-db.sh`의 검증된 전용 PG dump, Backend 건강 상태를 확인한 후에만 Frontend를 공개한다.
- `scripts/verify-public-https.py`는 신규 호스트의 TLS trust/hostname, 200/Ready, 비로그인 401, Origin 없는 login 403, 기존 PickNext TLS를 **익명·읽기 전용**으로 검증한다. 검증 실패 시 FolioSentry Frontend만 정지한다.
- 백업은 `~/.local/share/folio-sentry/backups`의 사용자 전용 파일(권한 600)이다. 인증 해시 포함 가능: Git/채팅/외부 전송 금지. 아카이브 가독성은 복원 검증이 아니다.
- `unpublish --confirm-stop-frontend-only`는 복구용으로 frontend만 stop한다. 기존 PickNext·Traefik 설정·공유기 포트·DB/볼륨 삭제 금지.
- 신규 TLS 검증과 CI는 브라우저 실인수/외부 도달성/장기 인증서 갱신의 증빙이 아니다.

## DEPLOY-02 운영 인수 완료 (2026-11-19)
- 사용자가 FolioSentry HTTPS 배포 및 브라우저 로그인/DEMO/로그아웃, 기존 PickNext 정상 동작 확인. 실행 Git 커밋 `808aaf9eb1a3a9913574bc7f1495d484379fdae1`.
- 운영 주소 `https://foliosentry.ramza.duckdns.org`. Backend Health, 신규 TLS 신뢰·호스트명, 익명 API 401, Origin 누락 로그인 403 확인 PASS. 최초 SSL 오류 6회 후 7차 재시도에서 PASS; 원인 임의 추정 금지.
- 사용자 전용 pg_dump 사전 백업·SHA256·아카이브 가독성 PASS. **백업 복원·정기화/원격 보관은 검증되지 않음.** 백업 파일과 인증 관련 정보는 절대 Git/채팅에 공유하지 않는다.
- 기존 PickNext TLS와 수동 기능 동작 유지. 기존 Traefik/공유기 변경 금지.
- 다음 개발은 먼저 격리 복원·정기 백업 준비, 이후 Phase 1 Watchlist/보유종목 CRUD. **운영 중 DB를 삭제·재생성하거나 인증 초기화 반복 금지.** 실 포트폴리오 데이터를 DEMO에 섞지 않는다.

## OPS-01 백업 복원 시험/정기화 경계 (2026-11-19)
- 운영 `foliosentry-prod` DB·Backend·Frontend·Traefik은 **현재 공개 운영 중**. 백업 복원 검증을 위해 운영 DB 복원, 컨테이너 재시작·중지, 볼륨 교체/삭제는 절대 하지 않는다.
- `scripts/verify-backup-restore.sh`는 *사용자가 선택한 비공개 archive*를 체크섬 확인 후 **새 postgres:17-alpine 컨테이너(네트워크 none/host port 없음/tmpfs 데이터)**에만 복원, schema/owner만 확인하고 임시 컨테이너를 정리한다. 실제 비밀번호 해시·세션 내용은 출력하지 않는다.
- `scripts/backup-db.sh --confirm-daily-backup`은 운영 DB에 읽기 전용 pg_dump만 수행하며 기존 `--confirm-prepublish-backup` 호환성을 유지한다. `scripts/run-daily-backup.sh`은 새 백업 검증 후에만 14일 이상 된 `daily-` 파일의 SHA256 검증된 쌍만 삭제. `prepublish-` 파일과 불명 파일은 절대 삭제하지 않는다.
- `ops/systemd/foliosentry-backup.timer`은 준비용 파일이며 MiniPC에 실제 등록/활성화되지 않았다. 사용자의 별도 승인 전 `systemctl --user enable/start`, `loginctl enable-linger` 금지.
- CI 격리 synthetic PostgreSQL 테스트 성공과 MiniPC 실 백업의 복원 성공을 혼동하지 않는다. 로그·GitHub·채팅에 DB/해시/백업 원본 전송 금지.
- 상세 운영 절차: `docs/BACKUP_RESTORE_OPERATIONS.md`.

## OPS-01 MiniPC 격리 복원 인수 결과 (2026-11-19)
- GitHub `main@1a836304328f67c2603453f1d24a7965d626f759`을 사용자 MiniPC에 fast-forward 후, 최초 prepublish 백업을 네트워크 없는 임시 PostgreSQL로 복원·인증 스키마·소유자 1명 검사 PASS.
- 사용자 출력: `FOLIOSENTRY_ISOLATED_RESTORE_TEST_PASS`, `FOLIOSENTRY_OPS01_RESTORE_PROBE_PASS`. 운영 DB/컨테이너 변경 없음. 정리 결과는 `ON_EXIT` 메커니즘이며 실제 임시 컨테이너 잔존 여부는 별도 확인 필요.
- 다음 단계는 **일일 백업 1건만 신규 생성하는 수동 검증**. 기존 백업을 삭제하는 `run-daily-backup.sh` 대신 `scripts/backup-db.sh --confirm-daily-backup`를 사용하여 보존 정책 적용과 분리한다.
- systemd 사용자 타이머는 아직 MiniPC에 등록/활성화되지 않았으며, 해당 설정 변경에는 별도 승인 필요.

## OPS-01 수동 Daily 백업 인수 결과 (2026-11-19)
- MiniPC `main@d65ff72b98b775096a560293386c49813ed7074c`에서 임시 복원 컨테이너 잔존 없음 PASS.
- 사용자 수동 `scripts/backup-db.sh --confirm-daily-backup` 실행: `FOLIOSENTRY_DAILY_BACKUP_VERIFY_PASS`, `BACKUP_SHA256_CHECK=PASS`, `FOLIOSENTRY_DAILY_BACKUP_MANUAL_PASS`. 운영 DB 데이터·기존 백업 불변.
- **이번 daily 백업에 대한 실 복원 시험은 미실행**(이전 prepublish 백업 복원 PASS와 구분).
- 사용자 systemd 타이머 03:30 및 14일 보존 코드는 GitHub에만 존재, 운영에 설치/활성화되지 않음. `Persistent=true`로 타이머 enable시 놓친 실행분이 즉시 실행될 가능성 있으니 명시 승인/사전검사 필요.

## OPS-01 자동 백업 타이머 활성화 (2026-11-19)
- 사용자가 MiniPC `main@394c60ab07361fa0af1fda7ec81f4495ec984595`에서 사용자 systemd 타이머 설치·enable --now를 실행하고 `FOLIOSENTRY_DAILY_TIMER_ACTIVATION_PASS` 확인.
- 서버 `Asia/Seoul`, user systemd active, `Linger=yes`, 기존 유닛 충돌 없음. 첫 예정 실행 2026-11-20 03:30 KST.
- 이 사실은 **타이머 활성화 PASS**이지 **첫 예약 백업 실행 PASS가 아님**. 첫 실행 후 서비스 상태, journal 성공 마커, 신규 daily 파일 SHA256 및 가독성 검증 확인 필요.
- 재설치, 재활성화, `systemctl --user start foliosentry-backup.service` 수동 중복 실행은 검증 필요 없이 하지 않는다. 기존 FolioSentry/PickNext/Traefik 변경 금지.

## 사용자 선택: 자동 백업 중지 및 기능 개발 우선 (2026-11-19)
- 사용자가 `systemctl --user disable --now foliosentry-backup.timer` 실행했고 `ActiveState=inactive`, `UnitFileState=disabled`를 최종 확인했다. 기존 백업 보존.
- 사전 승인 없이 백업 타이머 재활성화/백업 기능 확장/매 작업마다 백업 강제 권고 금지. 운영 데이터 손실 위험에 비례한 검증만 제안. 다음 개발 우선순위는 사용자가 체감하는 포트폴리오·시세 기능.

## Phase 1 P1 수동 종목/보유 관리 API — 개발 규칙
- 새 `portfolio_models.py`, `portfolio_api.py`, `20261119_portfolio01`은 **GitHub 코드 및 격리 CI에만 존재**, 운영 DB 스키마·서비스는 기존 AUTH revision 상태. 사용자 명시적 승인 없이 alembic upgrade, DB DDL, Backend/Frontend 재배포 금지.
- 종목을 수동으로 등록해도 공급자 검증을 거친 실제 상장 목록이 아님: `source=MANUAL_UNVERIFIED`. 외부 시세 없이 가격/평가액/손익은 항상 null·UNAVAILABLE. DEMO 수치를 실제 등록 내역에 섞지 않는다.
- 인증은 글로벌 Origin·CSRF·쿠키 미들웨어를 우회하지 않고, 금액/수량을 **문자열 Decimal·DB NUMERIC**으로 유지. Watch에는 수량/평균단가 저장 금지.
- 테스트는 격리 SQLite와 GitHub Actions 별도 PostgreSQL만 사용. 실 자산정보·인증정보·증권 API 토큰을 테스트/로그에 사용하지 않는다.
- API 및 배포 계약: `docs/PHASE1_PORTFOLIO_CRUD.md`. 다음 작업은 UI-03 연결, 이후 공급자 선정/시세. 기존 PickNext/Traefik/HTTPS/Auto-backup 설정 유지.

## UI-03 실제 종목 관리 Frontend — 운영 배포 금지 게이트 (2026-11-19)
- `RealPortfolioPage.tsx`, `realPortfolioApi.ts`는 GitHub 소스에만 작성된 **실제 수동 등록 종목 API 클라이언트**. 사이드바에 `실제 종목 관리` 메뉴를 추가하고 기존 `내 종목 (DEMO)`와 완전히 분리한다.
- 사용자 수동 종목 심볼은 `MANUAL_UNVERIFIED`. 외부 시세 연결 전 실제 등록 목록의 모든 quote/손익은 `UNAVAILABLE`/null이며 가짜 숫자 fallback 금지. DEMO와 실 수치를 같은 목록·통계로 혼합 금지.
- 프론트 Mutation은 AuthGate 내부 세션 CSRF로만 처리하고 `credentials=same-origin` 유지. 실 데이터·토큰을 브라우저 로컬 저장소 및 로그에 기록하지 않는다.
- **운영 DB의 기존 AUTH-only 스키마에 신규 Backend/Frontend를 그대로 배포하면 실패할 수 있으므로 배포 금지.** 운영 DB revision 확인, additive 마이그레이션, Backend/Frontend 차례 배포는 반드시 개별 사용자 승인 및 운영 안전 점검 후.
- 사용자가 자동 백업 timer를 `inactive/disabled`로 유지하길 선택함. 이 작업에서 백업 활성화·설정 변경 금지.
- 브라우저 인수는 합성 종목/금액으로 시행. 실제 계좌/매수가 정보를 인수검사용으로 사용하지 않음. 상세 `docs/UI03_REAL_PORTFOLIO.md`.

## Phase 1 운영 전환 사전검사 및 안전 게이트 (2026-11-19)
- 사용자가 MiniPC에서 `main@1f81e35416a9f29dc51a643c9dd16830fc61829b`을 ff-only 동기화한 뒤 읽기 전용 SQL로 `DB_STATE=PHASE1_SCHEMA_PENDING_EXPECTED`, `FOLIOSENTRY_PHASE1_PREFLIGHT_PASS`, `DATABASE_MODIFIED=NO`, `SERVICE_DEPLOYED=NO`를 확인.
- 기존 `scripts/deploy.sh publish`는 새 공개용/백업 강제 실행이며 **이미 공개한 서비스의 업데이트 용도로 절대 사용하지 않는다**. `db-init` 역시 신규 초기화 전용. 업데이트 시 마이그레이션 → Backend → Frontend만 별도 승인 단계로 진행.
- `scripts/phase1-live-preflight.sh`는 현재 운영 FolioSentry DB/Backend/Frontend 1개씩 running/healthy, 인증 revision·owner·신규 테이블 없음, 이미지 ID, 자동 백업 타이머 inactive/disabled를 **읽기 전용**으로 검증한다. 실제 배포 명령이 아님.
- 새 migration `20261119_portfolio01` 및 Backend/Frontend 이미지 교체는 사용자 명시 승인 없이는 금지. 다운그레이드·볼륨 삭제·기존 PickNext/Traefik 변경 금지.
- Frontend Nginx가 `backend`를 시작 시 정적 해석하므로 Backend 교체 후 Frontend 교체 전 일시적 502 가능. 무중단을 장담하지 말고 전환/복구 순서를 문서로 확인.
- 사용자가 자동 백업을 선택적으로 끄기로 확정함. `foliosentry-backup.timer`를 임의로 enable/start하지 않는다. 상세: `docs/PHASE1_LIVE_CUTOVER.md`.

## FastAPI 0.137+ 중첩 라우터 진단 및 Phase 1 배포 (2026-11-20)
- MiniPC 생산 이미지의 `app.main`/`app.portfolio_api` SHA256이 호스트 소스와 일치. `portfolio.router.routes=7`, `app.routes=8` 중 마지막 객체는 경로 속성이 없는 `_IncludedRouter`. 이는 FastAPI 0.137부터의 정상 중첩 라우팅 방식이며 라우트 누락이 아님.
- 릴리스 검사에서 `for route in app.routes: route.path`처럼 최상위 평면 라우트라고 가정하지 않는다. FastAPI 자체 `get_openapi(..., routes=app.routes)` 또는 실제 HTTP TestClient로 검사한다. 운영 외부 OpenAPI/docs는 계속 비활성.
- 사용자 MiniPC에서 2026-11-20 `20261119_portfolio01` 운영 DB 마이그레이션 PASS. 기존 계정 1명, 인증 세션 테이블 보존, 신규 종목/추적 테이블 0건. 운영 Backend/Frontend는 아직 기존 이미지로 정상 실행.
- 기존 롤백 이미지 SHA256은 보존돼 있고 새 Backend 이미지 SHA256은 `e2be1807608a1a9c5692df7fe20b506e43c7d338a6a2824fddc9a63a82cf4797`. 새 Backend/Frontend 빌드 완료; **이미지를 다시 빌드할 이유 없음.**
- 사용자가 이미 Backend·Frontend 운영 배포를 승인했으나 2026-11-20 평면 라우트 검사 AssertionError로 배포 전 중단됨. 수정된 `scripts/phase1-app-deploy.sh`는 운영 DB를 재마이그레이션하지 않고 기존 롤백 이미지를 보존하며 Backend→Frontend 순차 전환한다. MiniPC에서 사용자 명시 실행 전 컨테이너 변경 금지.
- 비인가 `/api/v1/instruments`, `/api/v1/tracked`는 401이어야 하며 로그인/세션/기존 DEMO/HTTPS·PickNext 검증 필요. 자동 백업 타이머 inactive/disabled 유지. `docs/PHASE1_LIVE_CUTOVER.md` 참조.

## 운영 브라우저 인수검사 방식 — 프로젝트별 독립 Work 가상 데스크탑 우선 (2026-11-20)
- 사용자의 선택: FolioSentry 운영 인수검사는 개인 PC에서 기존 실행 중인 로컬 Chrome/원격 디버깅 세션을 재사용하지 않는다. 다른 프로젝트(DQA·ALZI·MCPFlow 등) 테스트 및 로그인 상태와 충돌하지 않도록 **ChatGPT Work의 독립 클라우드 컴퓨터/브라우저**를 우선 이용한다.
- 운영 대상: `https://foliosentry.ramza.duckdns.org` (인터넷 공개 HTTPS). Work 가상 브라우저에서 실제 URL 접근·로그인 가능 여부부터 확인한다. 클라우드 측 접속이 불가능하거나 사용자 인증/MFA가 필요하면 가능한 범위만 확인하고 N/A를 명시한다.
- 인수검사 기본 범위는 **읽기 전용**: 로그인 후 최신 페이지, 기존 DEMO/메뉴, `실제 종목 관리` 메뉴, 빈 상태·수동 등록 폼·KR/US 선택, 실 시세 없음/손익 미계산, DEMO 데이터 분리, Network/JS 오류, 모바일 레이아웃. 운영 종목 등록/수정/삭제는 별도 사용자 승인 및 합성 테스트 데이터 범위가 확정될 때까지 금지.
- 브라우저 검증 PASS/FAIL/N/A는 서버 배포·CI의 PASS와 별도 결과로 보고. Work에서 DevTools나 모바일 에뮬레이션을 제공하지 않는 경우 검증했다고 주장하지 말고 N/A로 처리한다.
- 운영 계정 인증정보·쿠키·CSRF 토큰·개인 종목·수량/평균단가는 보고서·로그·스크린샷에 노출하지 않는다. Work의 사용자 제어 로그인 절차를 우선한다. 기존 로컬 Chrome 탭은 건드리지 않는다.
- 2026-11-20 MiniPC 실 배포: `main 84e94cf`, `FOLIOSENTRY_PHASE1_APP_DEPLOY_PASS`, `FOLIOSENTRY_PUBLIC_HTTPS_ACCEPTANCE_PASS`, `FOLIOSENTRY_PHASE1_ANONYMOUS_API_DENY_PASS`. DB 재마이그레이션 없음, PostgreSQL/Traefik/PickNext 변경 없음, backup timer inactive/disabled. **서버 배포 완료와 브라우저 인수검사 완료는 구분**한다.

## Phase 1 읽기 전용 Chrome 인수검사 완료 (2026-11-20)
- 사용자가 운영 공개 HTTPS에 로그인된 세션으로 읽기 전용 UI 검사를 완료: **PASS 7, FAIL 0, N/A 2**. 신규 실제 종목 관리 메뉴/빈 목록/KR·US 폼, DEMO 분리·시세 미연동 안내, 콘솔 오류 0건·390×844 모바일 가로 넘침 없음 확인.
- N/A: 실제 종목 행이 없어 시세·손익 개별 표시 미확인, Network 요청별 HTTP 상태 미확인. N/A를 자동 PASS로 바꾸지 않는다.
- 사용자는 종목 등록·수정·삭제나 DB/서버 변경을 하지 않음. 이후 운영 CRUD E2E 테스트는 합성 데이터와 별도 명시적 승인 필요.
- Phase 1 **운영 DB 마이그레이션·Backend/Frontend 배포·읽기 전용 Chrome 인수 완료**. 과거 문서의 '운영 미배포' 표현은 과거 시점 이력으로만 간주한다. 자동 백업 타이머 비활성 유지.
- 다음 기능 개발 우선순위는 KR/US 종목 식별자 검증과 시세 공급자 연동 설계. 인증정보·개인 보유 데이터 사용 금지. Work 독립 클라우드 브라우저 우선.

## MD-01 국내·미국 일봉 시세 공급자 조사 및 정규화 경계 (2026-11-20)
- 공식 문서 기반 공급자 비교: KIS 개인 계좌 + APP Key/Secret 기반 KR/US 조회, Twelve Data 미국 Basic 무료(일 800 요청)·KR Pro 유료, Alpha Vantage 국내 커버리지 확정 불가. 자세한 출처/조건: `docs/PHASE1_MARKET_DATA_ADAPTER.md`.
- MD-01 신규 파일 `backend/app/market_data.py`: 순수 비통신 KIS 국내/해외 일봉 OHLCV 파서와 공급자 Protocol. `backend/tests/test_market_data.py`: 합성 자료 전용. 실 KIS 계정·토큰·요청·DB 변경·시세 UI 연결은 **전혀 구현하지 않음**.
- `market+exchange_mic+symbol+currency` 검증, 국내 6자리 선행 0, 해외 시세 거래소 EXCD mapping, Decimal 문자열/8자리 소수, OHLC 일관성/중복/미래 거래일/미국 타임존 검증. 실패 시 전체 배치 거부.
- 수집시각 `fetched_at`을 공급자 갱신시각으로 위장하지 않고, 정규화 결과 `source_observed_at=None`, `is_final=False`, `availability=UNFINALIZED` 고정. 기존 운영 `quote.status=UNAVAILABLE` 유지, DEMO 수치 및 미확인 바를 실제 시세로 노출하지 않는다.
- 후속 KIS 실제 호출은 사용자 계정·사용 조건이 충족된 후 별도 PR, 자격증명은 MiniPC 비공개 파일/Docker secret으로만 처리, 로그/커밋에 저장 금지. 주문·잔고 API 금지. DB 마이그레이션·시세 활성화·운영 배포 모두 별도 명시 승인. 자동 백업 timer 비활성화 유지.

## MD-02 KIS 조회 전용 전송 코드 (2026-11-20)
- 사용자는 한국투자증권 **계좌를 보유**함. **2026-11-20 Open API 신청·실전 App Key/Secret 발급 및 최초 조회 PASS 사용자 확인**. 값·계좌번호·토큰 원문 절대 요청하거나 GitHub/로그/채팅에 저장하지 않는다. 사용자가 확인할 것은 신청 완료 여부만.
- `backend/app/kis_readonly.py`는 순수 opt-in 전송 모듈: 기본 `live_enabled=False`; KIS 고정 실전 HTTPS 호스트와 허용된 OAuth 토큰 POST/국내·해외 일봉 GET **3개 경로만** 사용. 주문·계좌·잔고 조회 차단.
- 비밀키는 사용자가 별도 비공개 0600 파일에 저장 후, 승인된 실행시에만 읽는다. HTTP 응답 원문·인증 오류 상세·키/토큰·계좌값 로그 출력 금지.
- 임시 단일 프로세스 토큰 캐시, 토큰 재발급 최소 6시간/일봉 요청 간 최소 1초/60회 상한. 재시작/병렬 세션 간 제어는 없으므로 **스케줄러/운영 UI/API에 연결하지 않는다**. 실제 호출은 개별 승인.
- 해외 `MODP=1` 수정주가/`0` 원주가, 국내 `FID_ORG_ADJ_PRC=0` 수정주가/`1` 원주가. 기존 정규화 `is_final=False` 유지. 출처·시각·원주가/수정주가·장마감 검증 전 가격/차트/평가손익 노출 불가.
- 기존 Phase 1 운영 배포·Chrome 인수 PASS(7/FAIL 0/N/A 2)와 별개로 GitHub 코드/CI만 개발. MiniPC 서비스·DB·Traefik/PinckNext·백업 타이머 불변. 참고 `docs/PHASE1_MARKET_DATA_ADAPTER.md`.


## MD-03 — 비확정 KIS 일봉 저장 경계 (2026-11-20)
- MD-03 코드는 독립 Draft PR로만 작성. PR #24/#25는 main 미병합이며 MD-03에서 강제 병합·배포하지 않는다. 실제 KIS 재조회·MiniPC 운영 DB 변경/마이그레이션은 **별도 명시 승인 없이는 금지**.
- `app.price_quality`: 공식 확인된 거래일별 KRX/미국 마감시각 + 보수적 2시간 대기, TZ/DST 검증, 주말·미래·오래된 데이터 거부. **공식 휴장·조기종료/공급자 관측시간 확인 전 finality 증명 아님**.
- `app.price_models.PriceBar`: 새 migration `20261120_pricebar01` 생성 코드. DB CHECK로 `quality_status='PARTIAL'`, `is_final=false`, `source_observed_at IS NULL` 강제. 운영 DB에는 설치하지 않는다.
- `app.price_repository`: 기본 쓰기 거부(`allow_write=False`), SQLAlchemy Session 외부 주입, 명시적 isolated-only 테스트, 멱등 INSERT 충돌은 같은 값만 NOOP, 다른 OHLCV는 보류·검토. 내부 commit·실 API 호출 없음.
- `analysis_eligible`은 항상 False. 부분 데이터로 포트폴리오 손익·실 시세·매매 신호·알림 노출 금지. 프론트 DEMO와 실 종목 가격 없음 표시 그대로 유지.
- CI 합성 DB에는 `folio_ci` loopback 전용 가드, migration 전후 isolated transaction/rollback 검증. 운영 MiniPC에서 `alembic upgrade head` 금지. 참조: `docs/MD03_PRICE_BAR_STORAGE.md`.

## MD-03B 공식 거래소 예외 일정 안전 기준
- 2026-11-19 KRX KOSPI/KOSDAQ은 수능으로 10:00~16:30 KST(일반 15:30이 아님). 한국거래소 KIND 공식 자료를 `app.exchange_calendar`에 기록했다.
- 미국 NYSE/Nasdaq 공식 자료: 2026-11-26 휴장, 2026-11-27 및 2026-12-24 13:00 ET 조기마감. 증빙 없는 날짜는 절대 개장/최종시세로 추정하지 않고 `PRICE_SESSION_CALENDAR_UNVERIFIED` 거부.
- 현재 명시된 날짜는 소수의 확인된 세션만 포함한 목록으로 전체 시장 달력으로 오인하면 안 된다. `PARTIAL`/is_final=false 유지. 실제 KIS/DB/운영 재검증 없이 새 날짜를 자동 허용하지 않는다.

## MD-02B KIS 첫 시세 조회 도구 게이트
- `backend/app/kis_first_probe.py`는 metadata-only 점검을 기본 권장한다. 네트워크는 `live` + 정확한 승인 문자열 + 개인 0600 비밀파일 + 단일 실행 마커를 만족한 경우에만 실행한다.
- 합성 테스트는 실제 KIS API를 호출하지 않는다. 키/토큰/가격/계좌 정보는 출력·저장·커밋하지 않는다. `live`는 사용자의 **별도 명시 승인** 없이 MiniPC에서 실행하지 않는다.
- 실패 및 빈 일봉 응답을 성공으로 간주하지 않고, 1회 시도 마커를 지우거나 자동 재시도하지 않는다. 다른 프로세스와 공유하는 토큰/전역 레이트리밋은 아직 미구현이며 운영 스케줄러·DB·UI에 연결하지 않는다.
- `docs/KIS_FIRST_READONLY_PROBE.md` 참고. 개인 MiniPC/Traefik/기존 운영/백업 정책 불변.


## MD-02C MiniPC 로컬 KIS 키 저장 준비
- `scripts/kis-secret-setup.py`는 GitHub Draft PR #24의 오프라인 도구다. 사용자가 PR을 검토·병합한 뒤 MiniPC 비루트 사용자 SSH에서 키를 **숨김 입력**한다. 0700 개인 폴더·0600 개인 파일을 생성하고 기존 키를 덮어쓰지 않는다.
- `check`는 메타데이터만 검사하며 키 원문을 읽지 않고 KIS 호출도 하지 않는다. 로그·Git·환경변수·명령행·화면공유·ChatGPT에 키/토큰을 노출하지 않는다.
- KIS 실전/모의 키는 구별해야 한다. 현 MD-02는 실전 API 도메인만 허용하므로 키 종류 확인 전 실제 호출 금지. 첫 실 API GET은 **별도 사용자 승인** 필수.
- 운영 서비스·Compose/DB/Frontend/Traefik/백업 타이머 및 MiniPC 파일은 승인 없이 건드리지 않는다. 상세 `docs/KIS_FIRST_READONLY_PROBE.md`.


## MD-02 실전 KIS 최초 호출 검증 결과 (2026-11-20)
- 사용자는 실전투자용 키임을 확인하고 토큰 POST 1회, KR/US 일봉 GET 각 1회를 승인. MiniPC 일회성 조회 로그: KR 비확정 bar 1건, US 비확정 bar 1건, `FOLIOSENTRY_KIS_FIRST_READONLY_PASS`. KIS 토큰 발급 카카오톡 안내 수신.
- KIS 안내에 따르면 접근 토큰 24시간 유효, 1일 1회 발급 원칙. **추가 API 호출·토큰 재발급 금지(별도 승인 전), 최초 일회성 마커 삭제 금지.**
- 실제 응답 경로/정규화만 PASS. `is_final=False`/관측시각 없음 유지, 실제 시세 표시·손익 계산·DB 저장 금지. 스케줄러 전에 프로세스 간 토큰 재사용 및 글로벌 레이트리밋 구현 필요.
- PR #24 Draft 유지, 운영 서비스·MiniPC 배포/DB 변경 없음. 상세 기록: `docs/KIS_FIRST_READONLY_PROBE.md`.


## MD-02D KIS 토큰 공유 상태 안전 게이트 (2026-11-20)
- GitHub 신규 파일 backend/app/kis_shared_state.py는 Linux 한 호스트/한 사용자/한 안전한 로컬 파일시스템에서만 flock 기반 토큰 및 API 호출 이력 제어를 제공한다. 상태파일에는 민감한 Bearer 토큰이 0600 권한으로 저장되므로 홈 백업 암호화/접근통제 필수.
- **기본 새 토큰 발급 거부**. 프로세스 재시작 후 토큰 공유는 새 상태 파일로 발급한 이후에만 가능하며 2026-11-20 최초 실호출 토큰은 이전 프로세스 종료로 재사용 불가. 그날 토큰을 재발급하지 않는다. 허용 플래그 활성화는 별도 사용자 승인 전 금지.
- 24h 토큰 발급 억제, 1.25초 일봉 간격, 최근 24h 요청 60회는 보수적 앱 내부 제한이며 KIS 전체 계정/다른 호스트 한도 보장 아님. 발급/요청 시도는 네트워크 이전에 영속화, 실패해도 자동 재시도 금지.
- MD-02D 코드는 live API/스케줄러/DB/Frontend/MiniPC에 연결하지 않고 합성 테스트만 허용. 운영 KIS 실제 요청·Compose 파일/볼륨 변경·DB migration/배포는 별도 승인. 상세 docs/KIS_SHARED_TOKEN_GATE.md.


## REVIEW ONLY: PR #24+#25+#26 임시 통합
- 이 브랜치는 각 Draft PR이 동시에 빌드·테스트 가능한지 확인하는 GitHub 리뷰용. main 병합/릴리스/실전 재요청/운영 DB migration 및 CLI 실행 지시 금지.


## 병합 전 코드 리뷰 수정 결과 — 2026-11-20
- PR #25: 공유 토큰 캐시 JSON이 유실된 뒤 기존 발급 이력이 사라지는 위험 수정. 별도 0600 `kis-ever-attempted-token.marker`를 토큰 요청 전에 영속화하고 상태 소실 시 `KIS_SHARED_STATE_LOST_AFTER_ISSUE`로 신규 요청 차단. 자동 복구/재발급 금지.
- PR #26: 한 배치의 앞쪽 price_bar INSERT 후 뒤쪽 가격 충돌 시 부분 저장이 남을 위험 수정. 내부 `session.begin_nested()` SAVEPOINT로 해당 배치 전체를 원자적으로 롤백. 외부 트랜잭션 commit은 여전히 호출자 제어.
- PR #27 합성 통합에서 두 위험의 추가 회귀 테스트를 함께 검증한다. 독립 Draft PR 병합과 운영 변경은 별도 승인. `docs/MD02_MD03_INTEGRATION_REVIEW.md` 참고.


## MD-02/03 오프라인 통합 품질 게이트 (2026-11-20)
- 검토 전용 PR #27 코드 스냅샷에서 분기한 `review/md02-md03-stdlib-offline-gate-20261120`에 `scripts/ci/md02_md03_offline_acceptance.py`를 작성했다. Python 3.12 표준 라이브러리만, 임시 파일 및 합성 키/transport만, socket.connect 차단. 실 계좌·KIS HTTP·운영 DB·Docker·로그인 API 접근 금지.
- `docs/MD02_MD03_STDLIB_OFFLINE_GATE.md` 참고. 저장소는 Private 유지. **로컬 테스트 실행 PASS 전까지 완료로 단정하지 말 것**. GitHub Actions 실제 실행 PASS, Alembic/실 PostgreSQL 검증을 대체하지 않는다.

 
## MD-03 임시 PostgreSQL 격리 테스트 도구 (2026-11-23)
- MD02/MD03 stdlib 합성 통합검증 10/10 PASS(사용자 MiniPC 제공 로그). 이것은 실제 PostgreSQL 동작 검증이 아니며 실 KIS API 호출도 아니다.
- scripts/ci/run-md03-isolated-docker.sh는 무조건 /tmp 격리 git archive에서만 실행. 기본 --preflight는 운영 docker image ID 읽기 전용 검사만, --run은 APPROVE_MD03_EPHEMERAL_DOCKER_ONLY 확인 문자열이 있어야 일회용 PostgreSQL+새 Python 테스트 컨테이너 2개를 실행한다.
- 운영 foliosentry-prod 컨테이너에서 실행/재시작/DB접속/환경변수·비밀파일 접근 금지. 운영 이미지 ID만 확인, 신규 PostgreSQL --network none, tmpfs, host port 없음. Python 테스트가 일회용 namespace만 공유한다.
- Docker pull/build/pip install/실 KIS·실 계좌/운영 마이그레이션/운영 Compose/배포 금지. scripts/ci/test_md03_isolated_docker_contract.py는 실행 명령의 핵심 안전 계약만 검사한다. 최신 지침 docs/MD03_ISOLATED_POSTGRES_LOCAL.md 참조.
- 이 스크립트는 아직 MiniPC 실행 PASS를 확인받지 못함. 따라서 실제 PostgreSQL 격리 E2E 결과는 미검증. 사용자가 승인하지 않으면 main, 운영 환경, KIS 토큰, 가격 시세·UI 불변. Private 유지.

## MD03-DB-LOCAL 1차 실패 및 재실행 게이트 (2026-11-23)
- 사용자 MiniPC: 격리 PostgreSQL READY와 사전 안전 계약 5/5 PASS, 그러나 가격 저장 테스트 시작에서 app.market_data ModuleNotFoundError 발생. 실 격리 DB E2E는 아직 PASS 아님.
- 운영 Backend 이미지를 재사용하되 신규 테스트 컨테이너에만 PYTHONPATH=/workspace/backend를 고정. migration 이전 archive app 전체 import 경로를 검증하고 다른 설치 패키지 경로면 중단한다.
- 이제 python -m scripts.test_price_bar_isolated_ci를 사용하여 아카이브 기반 단위 스크립트를 실행한다. 실제 KIS 호출/토큰/운영 DB 및 Compose 변경 절대 금지.
- 수정본 검증 PASS 전 main 병합/운영 배포 금지, Private 유지. 운영 컨테이너는 기존처럼 이미지 ID만 inspect, 테스트 전용 leftover는 읽기 전용 진단.


## MD03-DB-LOCAL 재검증 완료 및 기기 안정성 게이트 (2026-11-23)
- 사용자 MiniPC 최종 실행: bash -n PASS, 오프라인 안전계약 6/6 PASS, 격리 PostgreSQL READY, FOLIOSENTRY_MD03_ARCHIVED_SOURCE_IMPORT_PASS, SAVEPOINT 원자성/중복·충돌/DB 최종성 차단/전체 ROLLBACK/Alembic revision 20261120_pricebar01/잔여 0건 PASS. 최종 FOLIOSENTRY_MD03_ISOLATED_POSTGRES_INTEGRATION_PASS 및 FOLIOSENTRY_MD03_LOCAL_E2E_COMPLETE.
- 테스트 전후 라벨 기반 일회용 컨테이너 조회 0건. 1차 ModuleNotFoundError는 PYTHONPATH 및 -m 실행 수정으로 해결. 운영 DB/운영 서비스 건강 상태의 독립 확인, 실 KIS API/미국 일봉 최종성, GitHub hosted Actions 실행은 **미검증**.
- 이전 MiniPC 종료·재부팅 의심 사건의 원인은 미확인. 이전 부팅 커널 OOM/온도/전원/watchdog 로그와 시스템 상태를 읽기 전용 확인 전에는 추가 부하 시험과 운영 마이그레이션·배포 금지. 저장소 Private 유지; main 미병합.


## MiniPC 2026-11-23 부팅 복구 읽기 전용 점검 결과
- 사용자가 제공한 uptime/journalctl: 직전 부팅 기록 최종 2026-11-23 09:52:19 KST, 현재 부팅 시작 11:24:21 KST. 기록 간 1시간 32분 공백이 있으나 전원 종료/재시작/부팅 실패 원인은 **불명**. last 명령 미설치(별도 설치 불필요).
- 12:12 KST 기준 memory 14GiB 중 available 12GiB, swap 사용 0B. 운영 foliosentry-prod frontend/backend/db 3개 컨테이너가 모두 약 46분 Up(healthy). MD03 테스트용 라벨 컨테이너 0건.
- 이전 커널 경고 grep에서 현재 사고 직전 OOM/panic/열폭주 로그는 확인되지 않음. 출력된 11월 1일 초기 NMI watchdog 및 TSC 불안정 문구는 **11월 23일 사고 원인 증거가 아님**. 현재 메모리 여유가 사고 당시 OOM 가능성을 배제하지도 않음.
- 정지 원인 조사 전 신규 격리 Docker 부하 E2E/운영 마이그레이션/배포 금지. 09:40~09:55 KST 이전 부팅의 종료·OOM·watchdog·전원/디스크 오류 로그 추가 확인 후 안전 판단. 이번 MiniPC 자체 재부팅은 MD03 격리 DB E2E PASS와 별도 사건. Private 유지.


## MiniPC 2026-11-23 재부팅 추가 증거 (읽기 전용)
- 이전 부팅 09:40~09:55 종료/전원/OOM/커널 패닉/과열 로그 grep 결과 특이 이벤트 없음(그 범위·패턴 한정). 현재 부팅 11:24:26 KST systemd-journald가 system.journal corrupted or uncleanly shut down, renaming and replacing 경고 출력.
- 이는 시스템 저널의 비정상 종료/손상 정황이지 정전·하드웨어 고장·Docker 부하가 원인이라는 **확정 증거가 아님**. 커널/저널이 기록 못 하는 갑작스런 정지·강제 리셋 가능성도 남음.
- 추가 진단은 journalctl 읽기 전용과 네트워크/서비스 상태 관찰만. 신규 Docker 부하 테스트·운영 DB migration·배포 중지. Private 저장소 및 운영 서비스 유지.


## OPS-CI03 — CI × KIS 검토 스냅샷 (2026-11-23)
- 원본 CI `ci/usage-control-20261120@6843092`, MD02/MD03 검토 소스 `review/md02-md03-stdlib-offline-gate-20261120@20631a9`. 별도 **review/ci-kis-offline-integration-20261123** 브랜치에서만 소스 병합 미리보기. `main`/기존 PR #24~#27 미병합·Private 유지.
- CI 8 job: `changes` → 6개 선택 작업 → `ci-gate`. `changes`에서 기존 CI stdlib 단위 테스트 외 합성 KIS 통합 10개를 자동 실행하도록 결합(실 키·HTTP·DB 없음). MD03 임시 PostgreSQL CI 및 DB 최종성 차단 유지. AUTH browser는 수동 전용.
- `scripts/ci/test_ci_kis_combined_contract.py` 신규 4개 정적 계약 포함. 사용자 MiniPC에서 결합 스냅샷 unittest **38/38 PASS**, 별도 KIS 합성 **10/10 PASS**, YAML **PASS** 확인 (2026-11-23). hosted GitHub Actions 실행과는 별개.
- `docs/CI_KIS_COMBINED_REVIEW.md`가 통합 기준. 임시 검토 브랜치를 CI 복구 전에 PR 생성하지 않고, 유료 Runner·GitHub Actions 동작 검증을 주장하지 않는다. 실전 KIS 토큰·Quote·실계좌/잔고/주문, 운영 Docker/DB/Traefik/백업, live 시세·손익 UI 불변.
- 전원 문제는 가족 연락으로 집 전원 스위치가 꺼져 있었고 복구됐다는 정보 확보. **외부 전원 차단이 가장 유력**하지만 추정과 완전한 하드웨어 진단은 구분한다.


## OPS-CI04 38/38 + 10/10 최종 검증과 Draft 병합 경계 (2026-11-23)
- 검토 브랜치 `review/ci-kis-offline-integration-20261123@d2168a6`를 MiniPC의 별도 임시 archive에서 확인: CI unittest 38/38 PASS, KIS 합성 stdlib 10/10 PASS, YAML 파싱 PASS, 최종 `FOLIOSENTRY_CI_KIS_OFFLINE_GATE_PASS`.
- 병합 조정 계획 `docs/CI_KIS_MERGE_PLAN.md`: CI 최적화 우선 → Draft #24 → #25 → #26 → 통합 회귀 테스트 보존. 특히 #26의 `.github/workflows/ci.yml` 수정이 CI 최적화 워크플로를 덮어쓰지 못하게 최신 CI를 기준으로 충돌 조정할 것. 문서와 소스 경계 유지.
- 실제 hosted Actions, PR 승인/병합, 운영 스키마·서비스·실 KIS 연결과는 구분. 새로운 검토 브랜치는 main 병합 금지. Private 유지.


## OPS-CI05 — Private PR 병합 사전 시뮬레이션 (2026-11-23)
- `review/ci-kis-merge-rehearsal-20261123`에서만 `scripts/ci/merge_rehearsal.py`와 순수 unittest 6개, `docs/CI_KIS_MERGE_REHEARSAL.md`를 작성. 원본 결합 검토 브랜치 `review/ci-kis-offline-integration-20261123@0c1c22a`는 변경하지 않음.
- git2.39+ 사용자 MiniPC 원본 저장소 ROOT에서 실행. 정확한 GitHub private remote 확인 후 `--preflight`는 네트워크/파일 수정 없음, `--run`은 오직 /tmp TemporaryDirectory 내부 별도 bare git에 private GitHub branch **fetch만** 수행.
- main/CI/PR #24/#25/#26/결합본의 고정 40자리 SHA 검증, 23개 CI 및 KIS 핵심 코드 blob 비교, 7개 독립 `git merge-tree --write-tree --name-only`로 충돌 파일명/개수 진단.
- **pairwise 분석은 CI→#24→#25→#26의 실제 순차 병합을 재현하지 않음**. 충돌 발견 시 직접 조정 필요. 실제 GitHub merge/push/rebase/Actions dispatch/운영 Docker/KIS API/DB 접근 금지. 현재 검사 코드 작성 상태일 뿐 실 실행 PASS 미확인.
- 로드맵·병합 계획 최신 내용과 비밀정보/Private 유지 조건 보존. 새 테스트/검토 브랜치는 main에 병합하지 않는다.


## OPS-CI06 — 순차 합성 병합 사전검증 (2026-11-23)
- 기존 MiniPC pairwise 검사 6/6 PASS, PINNED SHA PASS, 핵심 CI/KIS 23개 blob MATCH. 7개 쌍 총 충돌 13건은 중복 포함이며 실제 고유 경로는 `AGENTS.md`, `docs/ROADMAP.md`, `.github/workflows/ci.yml` **3개**.
- `scripts/ci/sequential_merge_rehearsal.py`로 CI→PR #24→#25→#26을 임시 **bare Git**에서 단계별 `merge-tree`+임시 synthetic merge commit으로 순차 검증. 허용된 세 파일 이외의 충돌이면 fail-closed. 합성 충돌 해소는 결합 검토본의 같은 파일 Git blob을 임시 index에서 사용.
- 23개 핵심 코드와 3개 충돌 해소 파일 blob을 최종 통합 검토본과 대조. 통합 검토본에만 있는 후속 테스트는 자동 병합되지 않음. 중간 합성 merge commit은 미래 단계 문서가 선반영됐을 수 있으므로 **운영/실제 병합에 사용 금지**.
- `scripts/ci/test_sequential_merge_rehearsal.py`는 로컬 Git fixture와 무통신 계약 6개 포함. 새로운 순차 검사는 **아직 MiniPC 실행 PASS가 아님**. `docs/CI_KIS_SEQUENTIAL_REHEARSAL.md` 참고.
- 기존 CI 38/38+KIS 10/10+YAML 및 MD03 일회용 DB PASS는 유지하되, Github-hosted Actions 미검증. 원본 private GitHub 브랜치/PR/main, 운영 DB/KIS API/Docker 불변.


## OPS-CI06 후속 조회 오류 보정 (2026-11-23)
- 사용자 MiniPC에서 순차 합성 병합 unittest **12/12 PASS**, CI→#24→#25→#26 (충돌 0/2/2/3), 23개 핵심 코드 blob 및 3개 허용 해소 파일 **MATCH**. 최종 선택적 후속 테스트 파일 검사는 `SEQUENTIAL_FOLLOWUP_CHECK_FAILED`로 종료하여 전체 게이트는 FAIL.
- 원인: Git `cat-file -e tree:없는경로`는 종료 코드 128인데 스크립트가 1만 예상. `ls-tree --name-only`의 정상 0+빈 출력 패턴으로 변경하고 실제 임시 Git fixture 및 잘못된 응답 거부 테스트 2개 추가. 새 **14개 테스트 / 순차 최종 마커는 MiniPC에서 재검증 전**.
- 원본 PR/CI/통합 스냅샷/SHA/메인 및 운영은 불변. 합성 병합 결과로 실제 GitHub PR을 병합하지 않으며, 후속 통합 테스트 파일이 실제 개별 PR에 없으면 정상적인 follow-up 대상. hosted Actions 실행, 운영 DB 마이그레이션, 실 KIS 재호출 금지. Private 유지.


## OPS-CI07 — 순차 합성 검증 최종 PASS (2026-11-23)
- 사용자 MiniPC 원본 `ca705b0`: 오프라인 안전·회귀 unittest **14/14 PASS**, 고정 SHA 6개 PASS, 임시 bare Git CI→#24→#25→#26 순차 합성 4단계 완료. 충돌 0/2/2/3 = 합계 7건을 사전 승인된 문서 2개와 CI workflow 1개에서만 해소.
- 최종 핵심 코드 23/23 Git blob MATCH, 해소 파일 3/3 MATCH. 이전 `cat-file -e`의 128 오판을 `ls-tree`로 수정, 후속 5개 파일 미포함 **정상**, 최종 `FOLIOSENTRY_SEQUENTIAL_LOCAL_REVIEW_COMPLETE` 확인.
- **이 검사 완료는 main/PR 병합 승인 또는 hosted Actions PASS가 아님**. 후속 파일 5개는 독립 PR 연쇄로 자동 포함되지 않아 별도 통합 회귀검증 PR이 필요. `docs/CI_KIS_FOLLOWUP_INTEGRATION_PLAN.md` 참고.
- CI → PR #24 → #25 → #26 각각 최신 main 기준 실제 CI 검증/병합은 사용자 별도 승인 대기. 현재 Private, main/원본 PR/운영 DB/KIS 토큰/miniPC 불변.


## OPS-LOCAL-CI01 — Windows(WSL2) SHA 고정 로컬 CI 준비 (2026-11-23)
- GitHub-hosted Actions 사용량 한도 소진은 개발 중단 사유가 아님. Private Windows 전용 별도 clone + WSL2(Ubuntu, Python >=3.12)에서 `scripts/ci/local-gate.ps1` 또는 `python3 scripts/ci/local_gate.py` 실행. `backend/app/kis_shared_state.py`가 Linux `fcntl.flock`를 사용하므로 **네이티브 Windows Python 전체 KIS PASS 금지**.
- 로컬 게이트는 GitHub 공식 origin/40자리 HEAD SHA/clean tracked source를 확인하고, git archive 스냅샷을 Linux 임시 폴더에 격리한 후 작업. 운영 MiniPC와 사용자 worktree, GitHub main/기존 PR, 실제 DB·KIS·토큰·Docker 접근 없음.
- `offline`: GitHub CI stdlib 안전계약/병합 계약 + 합성 KIS 테스트. `full --install-deps`: 명시적 pip/npm 인터넷 의존성 다운로드 허용 후 임시 Backend pytest/compileall, Frontend npm test/typecheck/build 추가. 설치는 임시 공간에서만. 실 PostgreSQL migration, 운영 배포, GitHub Runner status는 **N/A**.
- 비밀정보 환경변수 상속 금지, 차단된 로컬 DB host/port 설정, 로컬 로그(0600)/SHA-명시 JSON 요약, 실패 시 nonzero. 네트워크가 OS 방화벽 수준으로 격리되는 것은 아님. 실제 테스트 PASS는 **아직 미실행**; `docs/LOCAL_CI_WSL.md` 참고.
- Cursor Agent에 전체 코드 탐색/빌드를 맡기지 말고 ChatGPT에서 GitHub 코드 관리 및 단일 터미널 명령 제시. `main`/PR 병합 및 운영 DB/키/배포는 사용자 별도 승인 필수, Private 유지.


## OPS-LOCAL-CI01 WSL Node 경로 보정 (2026-11-23)
- 사용자 Windows WSL2에 Git/Python은 있으나 Linux `node` 없음, Windows `npm` shim만 PATH에 있음. WSL용 Node.js `22.17.0`을 공식 nvm으로 사용자 로컬 `~/.nvm`에 설치하도록 안내.
- `scripts/ci/local-gate.ps1` 실행기는 직접 `wsl -- python3` 대신 Bash login shell을 시작해 `~/.nvm/nvm.sh`를 명시적으로 source한다. Windows npm 사용을 Linux Node 검증이라고 주장하지 않는다. 관련 정적 안전 테스트 1개 추가(총 8개 기대).
- 이 수정은 전용 Local CI 검토 브랜치에서만 수행. 원본 CI/MD02/MD03 PR, `main`, 운영 MiniPC, 실 KIS/DB·GitHub Actions 그대로. WSL 실제 PASS 확인 전에는 완료 판정 금지.
