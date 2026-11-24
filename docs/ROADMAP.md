# FolioSentry 구현 로드맵

진행 원칙: ChatGPT에서 요구사항/설계/검증 기준을 먼저 작성하고, Cursor에는 한 작업씩 최소 프롬프트로 구현시킨다. 모든 단계는 독립 테스트를 거치며 병합/배포는 명시적 승인 후 진행한다.

## Phase 0 — 검증과 초기 구조
- [ ] 국내·해외 일봉 시세 실제 계정별 자격/호출량/지연/수정주가 검증 (MD-01 공식 공급자 비교 완료, 실 API 검증 미실시)
- [ ] 국내·미국 뉴스 API 요금/약관/기사 메타데이터 검증
- [x] 최종 배포 대상으로 집의 개인 MiniPC 선정 (전용 PostgreSQL/HTTPS/소유자 인증 운영 확인: 2026-11-19)
- [x] MiniPC OS·사양·Docker/Compose·포트 점검 (2026-11-19, REVIEW_FLAGS=0)
- [x] 기존 PickNext/Traefik 네트워크 `proxy`, entrypoint `websecure`, resolver `myresolver` 확인 (2026-11-19)
- [x] FolioSentry 신규 DuckDNS 후보 주소와 PickNext의 IPv4 매핑 일치 확인 (2026-11-19)
- [x] 기존 PickNext TLS 신뢰 검증 PASS, 31일 잔여, FolioSentry 후보 SAN 미포함 확인 (2026-11-19)
- [x] Traefik myresolver **TLS-ALPN-01**, Docker 443 publish, ACME 저장소 마운트 확인 (2026-11-19)
- [x] FolioSentry 신규 호스트 TLS 인증서 체인·호스트명 검증 PASS (2026-11-19, MiniPC에서 실행한 자동 검사)
- [ ] 외부 모바일/LTE 등 **별도 공인망**에서 443 접근 확인 (현재 미검증)
- [ ] 기존 ACME 저장소 백업·복구 방법 확인
- [x] 신규 FolioSentry HTTPS 라우터/인증서 실검증 (2026-11-19, 초기 6회 SSL 검증 재시도 후 PASS)
- [x] FastAPI + React + PostgreSQL 최소 골격 및 Docker Compose
- [x] Backend/Frontend/typecheck/build/Compose/인증·백업 CI 통과
- **게이트**: 샘플 데이터로 API/DB/Frontend 연결, 실 API 키 커밋 없음

## Phase 1A — 데이터 모델·API 계약·Figma 연계
- [x] 시장·종목·보유/관심·시세·뉴스·신호 논리 모델 설계 (`docs/DATA_MODEL.md`)
- [x] REST API 및 Decimal/시간대/가용성 계약 (`docs/API_CONTRACT.md`)
- [x] 가상 KR/US 종목·뉴스·신호 디자인 미리보기 API (`/api/v1/demo/overview`)
- [x] Figma Make 디자인 의뢰 브리프 (`docs/FIGMA_MAKE_BRIEF.md`)
- [x] Figma Make React 소스 수신·구조 검토 (`docs/FIGMA_SOURCE_REVIEW.md`)
- [x] UI-01 Figma 디자인 소스 이식 (PR #4 병합 / CI PASS)
- [x] UI-02 데모 overview API 바인딩, 로딩/오류/시세 없음 처리 (`docs/UI02_DEMO_INTEGRATION.md`)
- [ ] 6개 화면 데스크톱/모바일 브라우저 인수검사 및 디자인 사용자 확정
- [x] UI-03 실제 보유·관심 CRUD 전용 Frontend 컴포넌트·API 연결 (GitHub/CI 단계, 운영 미배포)
- [ ] UI-03 실제 MiniPC 브라우저 인수검사 (운영 DB 마이그레이션 및 배포 별도 승인)
- **게이트**: 모의 데이터 API 테스트·CI 성공, 실 API/DB/운영 배포 변경 없음

## AUTH-01 — 개인 전용 로그인 (실제 개인 보유 데이터보다 먼저)
- [x] 1인 소유자 계정 모델 및 Argon2id 비밀번호 해시, 인터랙티브 최초 초기화
- [x] Backend 기본 거부 인증 미들웨어 + 세션 쿠키/CSRF/Origin/로그아웃
- [x] Figma 화면 로그인 게이트, 이전 세션 재확인 및 로그아웃
- [x] 인증 테스트 및 격리 PostgreSQL Alembic 마이그레이션 CI 구성
- [x] GitHub 인증 CI 및 운영 로그인/로그아웃·DEMO 대시보드 브라우저 수동 확인 (2026-11-19)
- [x] 운영 외부 HTTPS 브라우저 접근 및 모바일 뷰포트 390×844 기본 레이아웃 확인 (Phase 1 읽기 전용 Chrome 인수, 2026-11-20)
- [x] 집 MiniPC DuckDNS + 기존 Traefik HTTPS 인증 경로 확정 및 운영 연결
- [ ] VPN/2FA 등 추가 접근 보호 필요성 검토 (실 개인정보·투자정보 등록 전)
- [x] 별도 승인으로 DB 스키마, 소유자 1명, HTTPS 운영 배포 수행 (2026-11-19)
- **게이트**: 비인증 포트폴리오 API 접근 불가, 인증 없는 개인 데이터 저장/배포 금지
- 세부: `docs/AUTH_DESIGN.md`

## Phase 1 — Watchlist와 시세
- [x] P1: 수동 Instrument 등록·검색 API (시장+거래소+심볼), 중복 검증·미검증 출처 표시 (GitHub 코드·격리 CI)
- [x] P1: 보유/관심 등록·조회·수정·삭제 Backend API + 인증·Decimal 검증 (GitHub 코드·격리 CI)
- [x] P1: MiniPC 운영 AUTH01 DB schema·owner 읽기 전용 사전검사 PASS (2026-11-19)
- [x] P1: 운영 전용 preflight 및 단계별 전환·복구 계획 GitHub 준비 (운영 미변경)
- [x] P1: 승인된 운영 DB 추가형 마이그레이션 `20261119_portfolio01` 완료; 기존 인증·세션 보존, 신규 테이블 2개 (2026-11-20)
- [x] UI-03: 별도 실제 보유·관심 관리 UI + CSRF 보호 API 연결 (GitHub 코드)
- [x] UI-03 승인된 운영 Backend/Frontend 순차 배포 `main@84e94cf`, `FOLIOSENTRY_PHASE1_APP_DEPLOY_PASS` (2026-11-20)
- [x] UI-03 운영 읽기 전용 Chrome 인수검사: PASS 7 / FAIL 0 / N/A 2; 실제 종목 등록·수정·삭제는 수행하지 않음 (2026-11-20)
- [ ] 운영 합성 데이터로 실제 CRUD·보유↔관심 변경과 개별 종목 행 E2E 확인 (**별도 승인 필요**)
- [ ] Network 요청별 응답 HTTP 코드 직접 확인 (읽기 전용 가능 시)
- [x] MD-01: 한국투자증권 KIS/Twelve Data/Alpha Vantage 공식 문서 기반 KR·US 시세 공급자 비교 및 호출 전 확인 조건 정리 (2026-11-20, GitHub만)
- [x] MD-01: KIS KR·US 일봉 OHLCV 비통신 정규화 계약 + Decimal·거래소·시점·품질 경계 합성 테스트 (GitHub만)
- [x] MD-02: KIS 일봉 전용 GET·토큰 POST·고정 호스트 allowlist·비밀 파일 권한·레이트리밋·합성 transport 테스트 구현 (GitHub 전용, 비활성 기본값, 2026-11-20)
- [x] MD-02 한국투자증권 Open API 신청·실전 키 발급 확인 및 2026-11-20 사용자 승인 1회성 KR/US 일봉 조회 검증 (자동 수집·시세 표시·DB 저장 미적용)
- [ ] MD-02 토큰 공유 캐시·다중 프로세스 rate limit·장마감/지연/가격조정 정책 검증 (스케줄러 전에 필요)
- [ ] MD-03: 확정 검증 데이터용 price_bar DB migration, 적재·멱등·장 마감/품질 판단 (별도 승인)
- [ ] 외부 공급자 기반 Instrument 검색/식별자 매핑 (별도 공급자 검증)
- [ ] 국내·미국 일봉 시세 수집/중복 방지/수집 상태 표시
- [ ] 단순 종목 차트/최종 갱신 시각
- **게이트**: KR/US 시장 시간대·휴장일·결측 테스트, 정상 데이터만 완료 처리

## Phase 2 — 분석 신호
- [ ] 지표 계산(MA/RSI/MACD/ATR)
- [ ] 설명 가능한 초기 매수/매도 검토·관망·위험 경고 규칙
- [ ] 계산 근거·전략 버전/세션 보존
- [ ] 신호 이력과 신호 상태 UI
- **게이트**: 정적 fixture 재현성, 미래 데이터 참조 없음, 데이터 장애 시 신호 억제

## Phase 3 — 뉴스와 이메일
- [ ] 종목별 국내/미국 뉴스 수집
- [ ] 출처/시간/원문 링크, 중복 제거, 관련성 필터
- [ ] 이메일 알림 outbox, 개인 설정, 반복 발송 방지
- [ ] 일반 뉴스 일일 요약
- **게이트**: 레이트리밋/중복/실패 재시도/알림 멱등성 검증

## Phase 4 — 모바일과 AI
- [ ] Android FCM 수신, 종목 상세 연결
- [ ] 선택형 외부 ModelOps Gateway API adapter (사용 허용 여부/연결 보안/토큰/호출량 검증 뒤)
- [ ] 뉴스 요약·사실/해석 분리, Gateway 비활성화/장애 시 기본 기능 유지
- [ ] 중요 뉴스 이벤트 감지 및 선택적 즉시 알림
- **게이트**: 원문 추적 가능, AI 허위 수치/기사 생성 방지 확인

## Phase 5 — 신호 품질 검증
- [ ] 전략 백테스트 (거래비용/슬리피지/데이터 편향 고려)
- [ ] 기본 매수 후 보유 대비 MDD/손익/거래 빈도 비교
- [ ] 개인용 전략 설정 및 신호 신뢰도 분석
- **게이트**: 백테스트의 미래 참조·과최적화·선택편향 문서화

## MiniPC 배포 준비 (기능 완성 및 명시적 승인 후)
- [x] 안전 사전점검 스크립트/기준 문서 준비 (`scripts/minipc-auth-preflight.sh`, `docs/MINIPC_AUTH_PREVIEW_PLAN.md`)
- [x] 실제 MiniPC 리소스/포트/디스크 여유 점검 (읽기 전용, 2026-11-19)
- [x] Traefik·DuckDNS 연동 Production Compose 및 배포 도우미 구현·운영 적용 (PR #8, #10 병합)
- [x] 기존 Traefik의 실제 네트워크/entrypoint/certresolver 확인 (읽기 전용)
- [x] DuckDNS 신규 후보와 기존 PickNext의 IPv4 DNS 매핑 일치 확인
- [x] 기존 PickNext TLS 사전/사후 확인과 FolioSentry 신규 HTTPS 체인/호스트명 검증 (2026-11-19)
- [x] PostgreSQL 백업 실제 생성·SHA256·아카이브 가독성 및 격리 임시 DB 실제 복원 확인 (2026-11-19)
- [x] 운영 백업의 독립 임시 PostgreSQL 복원·인증 테이블/소유자 건수 검증 (2026-11-19)
- [ ] 별도 장소 암호화 백업·보존 정책 검증
- [ ] 개인 전용 인증/VPN 등 외부 접속 안전 방안 확정
- [x] 인증 DB 백업을 네트워크 없는 임시 컨테이너에 복원하는 기본 시험
- [ ] 전체 복구 절차·암호화·백업 보존 및 인증서 저장소 복원 검증
- [ ] 실제 운영 데이터 수집·알림 점검; 개인 자산/토큰 로그 유출 검사
- [ ] 필요 시 ModelOps Gateway 연결 실증 (승인·최소 데이터·장애 fallback)
- **게이트**: 배포 승인 전에는 MiniPC/회사 서버 어떤 환경에도 배포하지 않음

## 다음 Cursor 작업 (필요할 때만)
Figma Make 시안 승인 이후에만 `AGENTS.md`와 `docs/API_CONTRACT.md`를 참조하여 **확정된 단일 화면**의 UI 연결 작업을 지시한다. 별도 DB/시세 수집은 각각 독립 PR로 분리한다.

## DEPLOY-02 운영 공개 인수 게이트
- [x] 개인 MiniPC 전용 PostgreSQL 생성, 인증 테이블·소유자 1명 확인 (2026-11-19)
- [x] GitHub 내 전용 DB 백업/HTTPS 검증/Frontend 중단 보호 코드 작성
- [x] 새 공개 전 전용 DB 압축 백업 생성 + SHA256·아카이브 스트림 검증 (MiniPC 2026-11-19)
- [x] Backend Health, Frontend HTTPS, 신규 인증서, 익명 API 401·Origin 403, PickNext TLS 자동 확인
- [x] 사용자 브라우저에서 로그인 화면, ramza 계정 로그인, DEMO 대시보드, 로그아웃, 기존 PickNext 정상 확인 (2026-11-19)
- [x] 별도 격리 DB 복원 시험 (2026-11-19)
- [ ] 장기 ACME 저장소 백업·갱신 검토

## DEPLOY-02 실제 운영 인수 기록 — 2026-11-19
- 배포 Git HEAD: `808aaf9eb1a3a9913574bc7f1495d484379fdae1` (PR #10 병합).
- `FOLIOSENTRY_PREPUBLISH_BACKUP_VERIFY_PASS`, `BACKUP_SHA256_CHECK=PASS`, `ARCHIVE_READABILITY=PASS_NOT_RESTORE_TRIAL`.
- Backend `HEALTHY`; 신규 FolioSentry TLS 첫 6회 `SSLCertVerificationError` 재시도 후 인증서 체인/호스트명 확인 최종 PASS. 발급 지연이 원인이라고 단정하지 않음.
- 익명 API 접근 차단 401·로그인 Origin 누락 403·Frontend 200·Backend Ready 자동 PASS.
- 사용자가 브라우저에서 로그인, DEMO, 로그아웃, 기존 PickNext 정상 동작 확인.
- **2026-11-19 후속:** DB 격리 임시 복원 시험 PASS.
- **아직 미완료:** 정기 백업·오프사이트 보존, 외부망/모바일 검증, ACME 자동 갱신, 실 포트폴리오 CRUD 및 시세·뉴스·알림 API.
- 다음 권고 작업: **별도 격리 DB 복원 시험과 정기 백업 자동화**를 먼저 설계/검증하고, 이후 Watchlist/보유종목 CRUD를 진행. 운영 DB에 테스트 데이터/마이그레이션 직접 적용 금지.

## OPS-01 — 격리 복원·정기 백업 준비 (2026-11-19)
- [x] 운영 PostgreSQL 데이터/서비스를 건드리지 않는 임시 Postgres 복원 검증 스크립트 작성 (`scripts/verify-backup-restore.sh`)
- [x] 일일 백업(잠금·SHA256·아카이브 검증) 및 14일 오래된 daily 파일만 정리하는 코드 작성
- [x] systemd 사용자 서비스/03:30 로컬 시간 타이머 **설정 파일만** 작성 (MiniPC 미등록)
- [x] CI 합성 DB 생성→백업→임시 DB 복원→보존 정책 PASS 및 PR #12 병합
- [x] MiniPC 기존 prepublish 백업을 **별도 임시 컨테이너**에 실제 복원하고 schema/owner 확인 (2026-11-19)
- [x] MiniPC 일일 백업 1회 수동 실행 및 무결성 확인 (2026-11-19, 기존 파일 보존)
- [ ] MiniPC systemd 사용자 단위/시간대/Linger/충돌 읽기 전용 사전검사
- [x] systemd 사용자 타이머 설치/활성화, Linger=yes·다음 2026-11-20 03:30 KST 확인 (2026-11-19)
- [ ] 첫 자동 예약 실행(2026-11-20 03:30 KST) 성공·실제 백업 파일 생성·보존 규칙 확인
- [ ] 오프사이트 암호화·복원/보존·실패 알림, ACME 인증서 저장소 백업 별도 검토

## Phase 1 운영 Chrome 인수검사 — 2026-11-20

- 서버 배포 기준(별도 검증): `main@84e94cf22c62b7b34f3727831a5955a86db4b99a`, `FOLIOSENTRY_PHASE1_APP_DEPLOY_PASS`, 공개 HTTPS·인증·PickNext 회귀검사 PASS. 데이터베이스 마이그레이션 재실행 없음, 자동 백업 타이머 inactive/disabled.
- 사용자 제공 운영 브라우저 **읽기 전용** 검사: **PASS 7 / FAIL 0 / N/A 2**.
- PASS: 기존 로그인 세션 새로고침; 기존 DEMO 대시보드/메뉴 유지; 실제 종목 관리 화면; 전체/보유/관심 빈 상태; 한국(KRW)↔미국(USD) 전환과 거래소 선택지; 시세 미연동·손익 미계산·DEMO 분리 안내; JS 콘솔 오류 0 및 390×844 모바일 레이아웃 가로 넘침 없음.
- N/A: (1) 실제 종목 목록이 비어 있어 개별 종목 행의 시세·손익 표시 미검사, (2) Network 요청별 HTTP 상태 미검사(콘솔 네트워크 오류는 관측되지 않음).
- 운영 종목 등록·수정·삭제, DB/서버 설정 변경 없음. **읽기 전용 UI 인수 완료 ≠ CRUD E2E 검증 완료**.
- 다음 개발은 국내·미국 시세 공급자 검토와 종목 식별자 매핑/시세 상태 모델링을 우선. 실제 종목 행과 CRUD E2E 시험은 합성 데이터 및 별도 명시 승인 이후 진행.


## OPS-CI01 — GitHub Actions 무료 할당량/중복 실행 최적화 (2026-11-20)
- [x] 개인 Billing Actions 포함 컴퓨팅 $12/$12 소진 확인, 결제수단 없이 Private Actions 작업이 실행 전 차단되는 증상 분석
- [x] 기존 feat/** push + PR 중복 CI 및 매번 6 job 실행 문제 확인
- [x] Private 상태에서 비용 최적화 독립 브랜치 설계: PR(main)/push(main) 이벤트, concurrency 취소, 영역별 job route + CI gate + 합성 unittest
- [x] AUTH Chromium browser 수동 실행 전용으로 변경(릴리스 인수검사 때 명시 실행)
- [ ] 최적화 워크플로 로컬 YAML/라우팅/최종게이트 검사
- [ ] 정상 GitHub Actions 실행 가능 시 최적화 CI 6 job + 안정 게이트 PASS
- [ ] 사용자 병합 승인 이후 main 동기화 및 PR #26의 격리 DB migration CI 유지·재검증
- [x] Public 전환 위험 검토 완료: 운영 정보가 과거 Git 이력에 남아 있고 Actions 로그는 미검사. **최종 결정은 Private 유지**
- [x] 사용자가 FolioSentry 저장소 Private 유지 확정(2026-11-20). Public 전환·별도 Public 미러 생성 계획 없음
- 세부: `docs/CI_USAGE_CONTROL.md`. **CI 코드 브랜치 작업만으로 실제 운영 MiniPC/서비스/KIS/DB 변경 없음.**


## Public 저장소 전환 사전검사 (2026-11-20)
- [x] 현재 main 트리 내 홈 MiniPC/DuckDNS/Traefik 구성·운영 문서 노출 가능성 확인
- [x] Git 과거 객체의 민감한 파일명·자격증명 패턴·운영 주소를 값 노출 없이 분류하는 읽기 전용 로컬 감사 스크립트 작성
- [x] 공개 전 감사 도구 자체의 합성 unittest 추가(워크플로 경로 테스트와 함께 실행)
- [x] MiniPC 실제 로컬 이력 감사 및 사용자 결과 확인 (운영 흔적 79 Git blob 버전/12경로, 개인키 헤더 2건은 합성 코드 문자열; Actions 로그는 미검사)
- [ ] GitHub Actions 전체 과거 로그·아티팩트와 원격 전용 PR refs 추가 확인
- [x] 사용자 최종 선택은 Private 유지. 추가 공개 검증은 현재 개발의 필수 경로 아님


## OPS-CI01 사용자 MiniPC 로컬 재검증 (2026-11-20)
- [x] 커밋 `239f5c2716f3866b2072c6d5dad22ea8382ed15e`에서 `scripts/ci` Python 단위 테스트 **21/21 PASS**, `FOLIOSENTRY_CI_LOCAL_UNIT_TESTS_PASS` (사용자 제공 MiniPC 실행 로그)
- [x] `scripts/public-visibility-preflight.py --self-test` PASS, `FOLIOSENTRY_PREPUBLIC_SCANNER_SYNTHETIC_SELFTEST_PASS`
- [ ] Actions Runner 기반 실 CI는 무료 포함량 소진으로 아직 실행 검증되지 않음. YAML 자체의 별도 파싱/체크 및 GitHub Actions CI-gate 실동작 확인 필요
- [ ] 무료 할당량 회복/사용자 승인 전 PR 생성·반복 CI 재실행 금지. 기존 main/운영 서비스/키/DB 영향 없음


## OPS-CI02 — Private 유지·MD-03 안전 통합 준비 (2026-11-20)
- [x] 사용자가 저장소 Private 유지 결정. Public 전환 또는 Public 소스 미러 생성 작업 중단.
- [x] CI 최적화 브랜치에 MD-03 마이그레이션 파일과 격리 테스트 동시 존재 여부 확인(한쪽만 있으면 fail-closed), 가격 테이블/마이그레이션 revision 조건부 검증, 합성 DB 전용 테스트 사전 연결.
- [x] 오프라인 워크플로 계약 회귀 검사 작성: PR/push 트리거, 변경 영역별 조건, 모든 필수 작업, CI 최종 게이트, 보안상 중요한 PostgreSQL·배포·백업 검증 유지.
- [x] 보안 감사 스크립트만 수정 시 `changes`·`ci-gate` 위주로 경량 실행(합성 보안 테스트는 `changes`에서 검사).
- [ ] MiniPC 격리 임시 파일로 오프라인 CI 테스트 재검증(신규 계약 검사 포함), YAML 파서가 있다면 구조 파싱 추가.
- [ ] Actions 무료 제공량 갱신 후 6/6 hosted 검증 및 사용자 승인에 따른 `main` 병합.
- [ ] PR #24→#25→#26 통합 및 GitHub hosted 검증(실 KIS 재조회·운영 DB 업데이트·서비스 배포 별도 승인).


## OPS-CI02 오프라인 최종 검사 완료 (2026-11-20)
- [x] `11f6c508e712fd6f83fa73d25d2e69a86425b7ee` MiniPC 독립 임시 디렉터리 로컬 unittest **28/28 PASS**
- [x] `FOLIOSENTRY_PREPUBLIC_SCANNER_SYNTHETIC_SELFTEST_PASS`
- [x] `FOLIOSENTRY_YAML_PARSE_PASS` (사용자 MiniPC PyYAML 파싱)
- [x] `FOLIOSENTRY_CI_OFFLINE_GATE_PASS`
- [ ] GitHub Actions 무료 할당량 갱신 후 실제 PR CI 및 8개 작업의 선택 실행/최종 Gate 정상 동작 확인
- [ ] 사용자의 명시적 승인 후 CI 최적화 브랜치 병합 및 PR #24→#25→#26 순차 리뷰/통합
- [x] 저장소 Private 유지 — 사용자가 최종 확정


## OPS-PUBLIC-CI01 — Public 전환 완료 및 GitHub Actions 검증 (2026-11-23)
- [x] 사용자가 기존 `ramza2/folio-sentry` 저장소를 **직접 Public으로 전환**. GitHub API `private=false`, `visibility=public` 확인. 이전 Private 유지 결정은 변경됨.
- [x] Windows WSL2 Local CI FolioSentry 전용 폴더·테스트 보고서 삭제 완료. 해당 환경 재구축 불필요.
- [x] `main`의 `.env`/`.env.*` Git ignore 유지, 공개용 비밀 파일 패턴 보강. 운영 MiniPC의 실제 자격증명·DB·KIS는 GitHub와 분리.
- [ ] CI 최적화 별도 Draft PR에서 **GitHub-hosted Actions 실 실행**으로 변경 라우터/전체 작업/고정 `ci-gate` PASS 확인.
- [ ] 사용자 **별도 명시 승인** 후 CI 최적화 PR 병합 → PR #24 → #25 → #26 순차 병합 준비. 각 단계 최신 HEAD CI와 CI workflow/MD03 충돌 해소 필수.
- [ ] 과거 전체 Git refs 및 Actions 로그/아티팩트 비밀정보 전수 감사 별도. 공개 운영주소/인프라 단서는 현행 소스 일부에 남아 있음. 키 노출 의심 시 교체.
- [ ] 운영 KIS 자격증명 설치/실조회/시세 저장 및 운영 DB schema migration/배포는 각각 별도 승인.


## MD-02B — KIS 최초 실 조회를 위한 일회성 운영자 점검 (2026-11-20)
- [x] 계좌 및 Open API 신청·App Key/Secret 발급 완료 사용자 확인(2026-11-20; 실전/모의 구분은 미확인)
- [x] `backend/app/kis_first_probe.py`: 기본 metadata-only 검사, 명시적인 live 승인 문자열, 최초 1회 마커, 국내/미국 각 1개 일봉 조회, 시세·토큰·원문 출력 금지
- [x] `backend/tests/test_kis_first_probe.py`: 합성 데이터/가짜 전송만, 인증정보·외부 접속 없음
- [x] KIS 신청·키 발급 완료 사용자 확인(2026-11-20; 비밀원문 미수신)
- [x] MiniPC 0600 비밀 파일 준비·메타데이터 점검 PASS (2026-11-20 사용자 제공, 실제 API 호출 없음)
- [x] 사용자 승인 후 국내/미국 실제 조회 전용 최초 호출 성공 — OAuth 1회 / KR 1건 / US 1건, 2026-11-19 거래일 (2026-11-20 사용자 로그)
- [ ] 다중 프로세스 토큰 캐시/전역 rate limit/장마감 정책 확정; MD-03 가격 저장 이전 필수
- 문서: `docs/KIS_FIRST_READONLY_PROBE.md`. **이 코드/PR은 실제 API 호출이나 운영 배포 승인이 아니다.**


## MD-02C — MiniPC 로컬 KIS 키 등록 준비 (2026-11-20)
- [x] `scripts/kis-secret-setup.py` 대화형 숨김 입력·0700 폴더/0600 파일·기존파일 덮어쓰기 방지·메타데이터 전용 check 준비
- [x] `backend/tests/test_kis_secret_setup.py` 합성/오프라인 권한 및 실패 테스트 준비
- [ ] PR #24 리뷰 및 병합 승인
- [x] MiniPC 사용자 `setup` + `check` 실행 성공(2026-11-20, `FOLIOSENTRY_KIS_SECRET_SETUP_LOCAL_PASS_NO_NETWORK`, `FOLIOSENTRY_KIS_SECRET_METADATA_PASS_NO_CONTENT_READ_NO_NETWORK`; 사용자 제공 결과, 비밀값 미수신)
- [x] 사용자 실전용 키 확인 + 별도 실 시세 GET 승인 + 제한적 최초 호출 성공 (2026-11-20; 시세 최종성 미검증)
- 코드 준비는 운영 MiniPC 변경이나 KIS 실제 호출을 포함하지 않음.


## 2026-11-20 실제 KIS 최초 조회 인수 결과 — 사용자 제공 MiniPC 실행 로그
- 승인: 한국투자증권 **실전투자용** App Key/Secret, 조회 전용 3회(OAuth 토큰 POST 1회, 삼성전자 일봉 GET 1회, 애플 일봉 GET 1회). 사용자 명시 승인.
- GitHub PR #24 검증 커밋 `01703f507cde8010b99c217ffbf1ae5eb3fccc3a`의 도구를 임시 폴더에서 실행. main 배포·작업트리·DB·Compose 변경 없음.
- `KIS_PRIVATE_FILES_METADATA_PASS_NO_SECRETS_READ_NO_NETWORK`
- `KIS_KR_UNFINALIZED_BAR_COUNT=1`, `KIS_US_UNFINALIZED_BAR_COUNT=1`
- `KIS_FIRST_CALL_STATUS=READONLY_QUOTE_SHAPE_PASS_NOT_PRODUCTION_APPROVAL`, `FOLIOSENTRY_KIS_FIRST_READONLY_PASS`
- 대상 조회 거래일: 국내·미국 **2026-11-19**, RAW 가격. KIS 실제 OAuth 발급에 대한 한국투자증권 카카오톡 알림 사용자 수신.
- **성공 판정 범위는 접근 토큰 발급 및 국내/미국 일봉 응답 구조·정규화 성공뿐**. 실제 가격값·장마감 최종성·원주가/수정주가 정합성·실시간 지연·공급자 관측시각·장기조회는 아직 미검증. `is_final=False`, `source_observed_at=None` 유지.
- KIS 안내 메시지: 토큰 발급 시점부터 유효기간 **24시간**, **1일 1회 발급 원칙**, 잦은 추가 발급 시 이용 제한 가능. **재발급을 위한 probe 재실행 및 1회 마커 삭제 금지**.
- 후속: 실제 재호출 없이 합성 fixture로 전역 레이트리밋 및 다중 프로세스 토큰 공유·재기동 정책 설계. 본 PR은 여전히 미병합 Draft이며 시세 적재/운영 표시/주문 기능 없음.

## MD-02B/C: Public CI 기반 PR #24 통합 준비 (2026-11-23)
- [x] Public `main@afd9cb3` 기반 PR #24 코드/테스트 및 기존 검증 기록 보존 방향 확정; AGENTS·ROADMAP 충돌 조정
- [ ] PR #24 최신 SHA의 GitHub-hosted `CI gate` PASS 확인
- [ ] 별도 명시 승인 후 PR #24 `main` 병합; 운영 MiniPC·DB·실 KIS 조회는 본 PR 범위에서 제외


## MD-02D — KIS 공유 토큰/호출 예약 기반 (2026-11-20)
- [x] 2026-11-20 최초 실전 KIS 토큰 POST 1회 및 KR/US 일봉 GET 각 1회 성공 기록(사용자 제공 PASS, 데이터 UNFINALIZED)
- [x] 공유 상태 파일 모델과 프로세스간 flock, 24시간 토큰 발급 간격, 전역 일봉 간격 1.25초, 24시간 60회 내부 상한, crash-safe 선예약 코드 작성
- [x] 기본 발급 거부 및 독립 optional shared_state 연계로 기존 운영 미변경, 진짜 토큰/호출 없음
- [x] PR #25 GitHub CI 6/6 PASS (2026-11-20, synthetic tests only)
- [ ] PR #25 리뷰 및 병합 승인
- [ ] 운영 MiniPC 공유 상태 디렉터리/보안/암호화 백업 검토(별도 승인)
- [ ] KIS 최신 정책/실 사용량 외부 확인 후 토큰 발급/실 호출 별도 승인
- [ ] MD-03 장마감 최종성·price_bar DB 모델/적재·스케줄러 승인
- 상세: docs/KIS_SHARED_TOKEN_GATE.md


## MD-02D 리뷰 안전 보완 (2026-11-20)
- [x] 공유 캐시 JSON 소실 → 신규 토큰 발급 제한 우회 위험 식별
- [x] 독립 영속 0600 토큰 발급 시도 마커를 네트워크 전 생성, 파일 소실/복구 시 재발급을 fail closed 차단
- [x] 합성 회귀 테스트 2개 추가(기존 토큰·발급 실패의 상태 소실) — CI 재검증 대상
- [ ] 손상/유실 상태의 안전한 수동 복구 절차는 별도 승인·공식 발급 이력 검증 이후 개발

## MD-02D — Public Actions 최신 검증 (2026-11-23)
- [x] PR #24 `main@9e5cd61` 병합 완료, main Hosted CI `45129177429` PASS.
- [x] PR #25 공유 상태 기능 코드와 기존 Public/CI/보안 문서 충돌 해소 준비.
- [ ] PR #25 최신 SHA GitHub Actions Backend/CI gate PASS 확인.
- [ ] 사용자 별도 승인 후 PR #25 병합. 운영 KIS API/토큰 재발급/시세 수집/DB·Docker 배포는 본 PR 범위 밖.


## MD-03 — 일봉 시세 품질·격리 저장 경계 (2026-11-20)
- [x] KRX/미국 거래소 시간대 및 보수적 장마감+2h 제한, 미국 DST·미래/주말·결측/오래된 시세 품질검사 오프라인 코드 작성. 확정 거래일/종가 인정은 미구현
- [x] `price_bar` SQLAlchemy 모델 + 추가형 `20261120_pricebar01` migration 코드 작성 (기존 표/행 불변, 최종시세 DB CHECK 차단)
- [x] 멱등 단일 거래세션 INSERT: 동일 시세 NOOP, 다른 시세 충돌 발생, 불확정 PARTIAL 고정, 실제 신호/UI 노출 금지
- [x] 합성 PostgreSQL CI 격리 migration 및 롤백 테스트 코드 준비 (전용 `folio_ci`만 허용)
- [x] MD-03 GitHub Actions CI 6/6 PASS 및 격리 PostgreSQL 마이그레이션·멱등·DB 확정시세 차단·롤백 검증 완료 (2026-11-20)
- [ ] MD-03 코드 리뷰와 병합 승인
- [ ] PR #24/#25는 2026-11-23 `main` 병합 완료, PR #26은 별도 Draft 유지
- [ ] 공식 휴장/조기 종료 및 공급자 시세 관측/확정/수정주가 검증
- [ ] **별도 승인 후에만** MiniPC 백업→격리 복원→운영 DB migration 및 배포
- [ ] 확정된 시세만 포트폴리오 화면/손익·신호로 노출 (MD-03에서는 불가)
- 상세: `docs/MD03_PRICE_BAR_STORAGE.md`

## MD-03B — 공식 시장일정 예외 검토 (2026-11-20)
- [x] 한국거래소 KIND 근거 2026-11-19 수능일 정규장 종료 16:30(KST) 반영, 기존 15:30 가정 교정
- [x] NYSE/Nasdaq 근거 2026-11-26 휴장, 2026-11-27·12-24 13:00(ET) 조기 종료 일정 검증·코드 작성
- [x] 미증빙 거래일 전면 차단하는 제한적 명시 세션 화이트리스트, EST/EDT 변환 테스트 작성
- [ ] 전체 휴장·특수 거래일 캘린더와 공급자 시세 최종성 검증 — 현재 소수 날짜만 검증
- [ ] PR #26 통합 CI 및 코드 리뷰, 운영 변경은 별도 승인


## MD-03 리뷰 원자성 보완 (2026-11-20)
- [x] 다중 일봉 배치 중간 충돌 후 일부 앞쪽 INSERT가 남을 가능성 식별
- [x] 저장 함수 내부 SAVEPOINT 도입하여 충돌 시 배치 전체 원자적 롤백
- [x] 추가 격리 PostgreSQL 합성 테스트: NEW ADJUSTED + conflicting RAW → 저장 0건(기존 RAW 유지)
- [ ] PR #26 CI 회귀검증 및 병합 승인

## MD-03 GitHub Actions PR #26 통합 준비 (2026-11-23)
- [x] CI 최적화 PR #28/최초 조회 PR #24/공유 토큰 PR #25 `main` 병합, 각 main CI PASS (PR #25 main CI #45130169347).
- [x] PR #26의 독립 MD-03 코드 8개 및 데이터 모델 문서 원본 blobs 보존, `AGENTS.md`·`docs/ROADMAP.md` 충돌 조정.
- [x] 최적화된 main CI 유지: PR #26의 구형 Workflow 덮어쓰기 금지; MD03 migration+test 양쪽 존재 fail-closed, 조건부 isolated PostgreSQL 테스트가 실행되도록 설계.
- [ ] 새 PR #26 HEAD의 Hosted Backend + auth-db-migration + CI gate 실제 PASS 확인.
- [ ] 사용자의 별도 명시 승인 후 PR #26 `main` 병합. 운영 MiniPC DB migration/실 시세 GET/배포는 별도 승인.


## MD-04A — KIS 합성 수집→격리 저장과 비확정 시세 공개 차단 (2026-11-23 최신)
- [x] PR #28 CI 최적화, PR #24 최초 조회, PR #25 공유토큰, PR #26 PARTIAL price_bar 저장 구조 main 병합. main 7ced35d, Hosted CI #45132743967 PASS.
- [x] 기존 DB는 PARTIAL/is_final=false/관측시간 NULL 강제. portfolio_api 시세 UNAVAILABLE·손익 NULL, Frontend 숫자 시세 응답 거부를 확인.
- [x] MD-04A 오프라인 intake 계약·KR/US 합성 테스트 코드 준비.
- [x] Fake KIS token POST 1 / 한국·미국 일봉 GET 각 1 → 정규화/품질 → 합성 DB PARTIAL 저장·롤백 테스트 코드 준비.
- [ ] MD-04A 신규 Draft PR의 GitHub-hosted Backend, auth-db-migration, CI gate PASS 확인.
- [ ] 사용자 별도 명시 승인 후 MD-04A main 병합.
- [ ] MD-04B 공급자 최종성·원천 관측시각·시장 일정·원주가/수정주가 증빙, 버전드 스키마 설계/검증.
- [ ] MD-04C 인증 시세 조회 API/Frontend/손익 UI와 오래된·불확정 가격 차단 E2E.
- [ ] 운영 DB 백업/격리 복원/마이그레이션, KIS 실조회, 자동수집/배포는 각각 별도 승인.
- 참조 docs/MD04A_OFFLINE_INTAKE.md.


## MD-04B — 공급자 최종성 증빙 결손 진단 (2026-11-23)
- [x] MD-04A PR #29 사용자 승인 병합: main@23399f6, Hosted CI #45135554431 PASS. 운영 환경 미변경.
- [x] KIS 국내 기간별시세 원주가/수정주가 요청값과 해외 MODP 설명의 공식 샘플 확인. 해외 값 의미와 공급자 관측·정정 정책은 추가 증빙 필요.
- [x] MD-04B 순수 비가격 FinalityGapReport 및 요청 RAW/ADJUSTED 불일치 차단 코드·합성 단위 테스트 작성.
- [ ] MD-04B Draft PR GitHub-hosted backend/CI gate PASS 및 리뷰.
- [ ] 사용자 명시 승인으로 MD-04B main 병합 (운영 MiniPC DB/시세 접근/배포 제외).
- [ ] KIS 원천 관측시각·최종 종가 확정·정정 가능 기간·기업행동·시세 접근권한 1차 근거 확보.
- [ ] 버전드 finality 정책, 조정주가 처리 및 DB VALID 전이 설계는 증빙·운영변경 승인 이후 별도 PR.
- [ ] MD-04C 실제 API/Frontend 연결·가격 표시/손익·신호/알림은 별도 사용자 승인 전 금지.
- 상세: docs/MD04B_FINALITY_EVIDENCE.md


## MD-04C1 — 실제 등록 종목의 비가격 품질 상태 UI (2026-11-23)
- [x] MD-04B PR #30 사용자 승인 main 병합: 020e065, post-merge GitHub CI #45137148434 PASS. 운영 미변경.
- [x] 순수 Backend QuoteMask 계약: MD-04B 결과 None→UNAVAILABLE, PARTIAL→UNFINALIZED, 위조된 finality/promote/형식 차단, 금액·종목·원천시각 노출 없음.
- [x] Frontend status-only 네 가지(UNAVAILABLE, UNFINALIZED, STALE, ERROR) 엄격 파서·한국어 상태 표시 및 실 목록·폼 유지. 현재 운영 API는 계속 UNAVAILABLE.
- [x] Backend/Frontend 합성 단위 테스트, API 계약과 AGENTS 문서 작업.
- [ ] MD-04C1 Draft PR 최신 GitHub-hosted Backend, Frontend, CI gate PASS 확인.
- [ ] 사용자 별도 병합 승인 이후에만 main 병합. 운영 MiniPC 앱 배포, DB migration, 실 KIS 호출, 실제 가격/손익/신호/알림 연결은 별도 승인.
- [ ] MD-04C2 인증 상태 전용 API 연계 설계 및 공급자 품질 상태 기록. 검증 완료된 FINAL/CURRENT 가격 공개는 아직 미구현.
- 세부 docs/MD04C1_QUALITY_UI_CONTRACT.md.


## MD-04C2 — 로그인 세션 보호 시세 품질 상태 API (2026-11-23)
- [x] MD-04C1 PR #31 승인 병합: main 9422bea, GitHub Actions #45139488106 PASS, MiniPC 운영 변경 없음.
- [x] 기존 tracked/기본 종목 테이블만 읽는 GET /api/v1/tracked/{tracked_id}/quote-status 계약 작성 (기본 UNAVAILABLE + null, 엄격 response_model).
- [x] Frontend '상태 확인' 명시적 클릭 조회, same-origin/no-store, tracked ID와 비가격 상태 검증 및 실패 안전 처리.
- [x] 합성 SQLite/FastAPI 보안·오류·스키마와 Frontend adapter 회귀 테스트 작성.
- [ ] MD-04C2 Draft PR 최신 GitHub-hosted Backend/Frontend/CI gate PASS 확인.
- [ ] 사용자 별도 병합 승인 후에만 main 반영. 운영 MiniPC 배포·DB migration·KIS 토큰 발급·실조회·가격/손익/알림 공개 금지.
- [ ] MD-04C3 실제 공급자 품질 메타데이터 기록 및 확정성 승인 체계 검토. 가격 공개 전 가격기준·원천 관측·휴장/기업행동 검증 필요.
- 상세 docs/MD04C2_AUTH_QUOTE_STATUS.md.


## MD-04C3 — 비확정 공급자 품질 증빙 분리 저장 (2026-11-23)
- [x] MD-04C2 PR #32 사용자 승인 병합 main@77ade4e, post-merge Hosted CI #45141141642 PASS, 운영 미배포.
- [x] 신규 price_quality_evidence version MD04C3_V1 모델/추가형 20261123_quality01 migration/DB CHECK 코드 준비. price_bar PARTIAL-only 제약 불변.
- [x] 명시적 allow_write, 단일 price_bar·정책 고정, 멱등/모순 충돌 차단, 메타데이터만 저장하는 repo 및 합성 테스트 작성.
- [x] GitHub-hosted PostgreSQL folio_ci 전용 마이그레이션 HEAD, 0행 확인, 합성 KR/US 증빙, 최종성/공개 위조 CHECK, 전 행 rollback 테스트 연결.
- [ ] MD-04C3 Draft PR 최신 Backend/격리 PostgreSQL/CI gate PASS 확인.
- [ ] 사용자 별도 명시적 승인 후 main 병합. MiniPC 운영 DB migration·KIS 호출/토큰·배포·가격/손익 공개 승인은 별도.
- [ ] 품질 증빙의 외부 출처, 공급자 관측시각, 원주가/수정주가 의미, 기업행동/정정 이력에 대한 승인 가능 근거 수집. 최종성 v2 전이는 증빙 완료 후 별도 PR.
- 상세 docs/MD04C3_EVIDENCE_STORAGE.md.


## MD-04C4 — 자료 출처·버전·정정·철회 이력 (2026-11-23)
- [x] MD-04C3 PR #33 사용자 승인 main@d281b3b 병합, Hosted CI #45142866026 전체 PASS, 운영 미변경.
- [x] 신규 가격-분리 evidence_reference_revision 모델/추가형 migration 20261123_quality02, 기존 가격·품질 DB 제약 불변.
- [x] KIS/거래소 제한 HTTPS 출처·문서 버전·SHA-256 무결성 지문·RECORDED/CORRECTED/RETRACTED 순서/이전 해시 연결 및 철회 후 차단 구현.
- [x] 명시적 승인형 저장소(동일 기록 멱등, 모순·순서 위조 거부), DB UPDATE/DELETE 트리거, 합성 PostgreSQL rollback 검증 작성.
- [ ] MD-04C4 Draft PR 최신 Backend/격리 PostgreSQL/CI gate PASS 확인.
- [ ] 별도 승인 후에만 main 병합. MiniPC DB migration·실 KIS/원문 조회·운영 배포·공개 기능은 각각 별도 승인.
- [ ] 공급자 관측시각·최종종가·정정 규정·RAW/ADJUSTED·기업행동 근거를 수동 확인하고 독립적으로 검증. 링크/해시 자체는 증명 불가; FINAL 승격 금지.
- 문서 docs/MD04C4_REFERENCE_HISTORY.md.


## MD-04C5 — API별 공식자료/가격조정/최종성 증빙 결손 오프라인 검토 (2026-11-23)
- [x] MD-04C4 PR #34 승인·병합 main@1a9f95c, post-merge CI #45146478310 PASS. MiniPC 미배포.
- [x] KIS 공식 upstream commit 74b0a082fa67a0be5bf53f561719c853890ed2df 고정 후 KR itemchart와 US dailyprice 공식 예제/설정/백테스터에 대한 5개 소스·Blob SHA 검토.
- [x] 다른 KR 일자별 엔드포인트의 FID_ORG_ADJ_PRC 설명 불일치 감지, US MODP 값별 공급자 증빙 부재 문서화. 이력 링크/해시는 가격·최종성 증명이 아님.
- [x] endpoint scoped 수동 문서 메타데이터 검토 입력 검증, MD04B 결손 6개 유지, FINAL/VALID/공개 불허 순수 진단·오프라인 합성 테스트 작성.
- [ ] MD-04C5 Draft PR 최신 Backend pytest/compile 및 hosted CI gate PASS 확인.
- [ ] 별도 사용자 승인 후에만 main 병합. MiniPC DB migration/운영 배포/실 KIS 호출/가격·손익 공개는 각각 별도 승인.
- [ ] 실제 API/거래소별 수정주가·최종 종가 정책/원천 관측/정정·기업행동의 공급자 문서와 개별 종목 처리 1차 근거 확보. 근거 없는 finality 승격 금지.
- 상세 docs/MD04C5_OFFLINE_SOURCE_REVIEW.md.


## MD-04C6 — 공급자 최종성 증빙 확보 절차 및 승인 분리 게이트 (2026-11-23)
- [x] MD-04C5 PR #35 승인 병합 main@cae0695, Hosted CI #45150651288 SUCCESS. MiniPC 미배포.
- [x] 공급자/거래소의 7개 필수 근거 질문(원천 관측, 최종 종가, API별 가격기준, 정정창, 기업행동, 공급자 세션범위, 거래소 특수일정)을 국내·해외 각 엔드포인트별로 문서화.
- [x] MD04C5 결손/비승인 상태를 재검증하고 요구항목·출처 유형·참조 코드/문서지문/버전·시각·철회를 검사하는 fail-closed 오프라인 handoff 함수 작성. 참조 후보가 모두 있어도 HUMAN_REVIEW_REQUIRED/HOLD_UNVERIFIED만.
- [x] 공급자 공식 원문 수령→독립 기술 검토→데이터 정책 검토→v2 정책 별도 PR→운영승인 프로세스와 자료 비공개·보존 경계 문서화.
- [x] Backend 순수 합성 테스트에 cross-endpoint, 공급자/거래소 증빙 혼동, 철회, 위조된 승인/시각/지문, 비가격 UI 계약 유지 회귀 추가.
- [ ] MD-04C6 Draft PR 최신 GitHub-hosted Backend/CI gate PASS 확인.
- [ ] 별도 사용자 병합 승인 후에만 main 병합. MiniPC 운영 DB migration·실 KIS 호출/토큰·배포·가격·손익·알림/시그널 공개 승인은 별도.
- [ ] 실제 KIS 담당자로부터 7개 범주에 대한 1차 근거 확보 및 2인 검토 절차 별도 승인. 근거 미확보 시 현행 MD04B 6개 blocker 모두 HOLD.
- 상세 docs/MD04C6_PROVIDER_EVIDENCE_HANDOFF.md.


## 우선순위 전환 — MD-04C7 생략, MD-05 실제 시세·포트폴리오 구현 (2026-11-23)
- [x] 사용자 지시로 MD-04C7 공급자 공식 증빙 요청서 개발 **생략**. 개인용 서비스의 실 시세·평가손익·알림 기능 우선.
- [x] MD-04C6 PR #36 사용자 승인 main@cc9a4ec 병합, Hosted CI #45152250929 PASS; 운영 MiniPC/KIS 실조회 없음.
- [x] MD-05A 첫 vertical slice: owner/CSRF 보호 수동 KIS 일봉 참고 종가 POST, capability GET, 등록 종목 화면 버튼·비확정/STALE/UNAVAILABLE 표시, 기존 KIS 공유 호출 한도·토큰발급 보호 재사용. 2중 운영 플래그 기본 비활성.
- [x] 실제 현재가와 과거 일봉의 명칭 분리. 본 단계에서 PnL·실시간 시세·신호·알림·자동 수집·DB migration 구현하지 않음.
- [x] Backend + Frontend 합성 데이터·인증·게이트·오류·비가격 손익 계약 테스트 및 안전 운영 설정 문서 작성.
- [ ] MD-05A Draft PR 최신 Backend, Frontend, CI gate PASS 확인.
- [ ] 별도 사용자 승인으로 main 병합; MiniPC 배포/환경변수 활성/실 KIS 신규 토큰/API/실시세 UI 공개 승인과 구분.
- [ ] MD-05B 수동 **현재가** API(KR/US 계약·시간외/통화·신선도·호출 제한) 도입, 실응답 안전성/비용·권한 검토.
- [ ] MD-05C 개별 종목 평가손익 계산(소수 정확도, 통화/환율/기준시각, 입력값 검사), 실 시세와 DEMO 분리, 알림/신호는 별도.
- 상세 docs/MD05A_MANUAL_KIS_DAILY_REFERENCE.md.


## MD-05B — KIS 제공 현재가 수동 조회 (2026-11-24)
- [x] MD05A PR #37 승인 후 main@a1a4d58 병합, postmerge Actions #45303574289 Backend 365 / Frontend 29 PASS. MiniPC/KIS 실호출 없음.
- [x] KIS 공식 upstream commit b0a0d33b7e5f863a8f3c6790f50adb840829c806 KR 주식현재가/US 현재체결가 API(TR·파라미터·가격 필드) 검토 및 문서화.
- [x] 신규 읽기 전용 `KisReadOnlyCurrentProvider`, 기존 토큰·호출 제한 shared state에 고정된 2개 현재가 TR/path만 추가.
- [x] 로그인+Origin+CSRF 수동 현재가 POST와 capability GET, 두 개의 기본 비활성 운영 플래그, 신규 토큰 기본 비허용. Provider 원천시각·지연/개장 상태 UNKNOWN 및 수신시각만 표시.
- [x] Frontend 현재가 버튼/참조 일봉 버튼 분리, 시세 응답 문자열 엄격 검증, RealTracked.quote/PnL/알림/DEMO 분리, 합성 KR/US 5거래소 및 오류 테스트.
- [ ] MD05B Draft PR Backend/Frontend typecheck/build, change impact/CI gate PASS 확인 및 별도 병합 승인.
- [ ] 실 KIS API/토큰/운영 배포·가격공개 승인은 별도 검토. 공급자 체결시각·미국 지연/유료시세 권한과 시장별 세션 경계를 실 응답으로 확인.
- [ ] MD05C 개별 보유수량·매입단가 기반 평가손익(Decimal 정확도, 통화 분리, 가격 신선도/이상 응답 차단), 이후 알림/시그널 별도.
- 상세 docs/MD05B_MANUAL_CURRENT_QUOTE.md.


## MD-05C — 보유종목 참고 평가손익 및 통화별 집계 (2026-11-24)
- [x] MD05B PR #38 승인 main@2840fa5 병합, postmerge #45308087479 SUCCESS (Backend 432 / Frontend 35).
- [x] KIS 현재가 + 직접 입력 수량/평균단가 기반 정확한 소수점 평가금액·매입금액·미실현 참고 손익·수익률.
- [x] KRW/USD 별도 집계, 로드한 보유 종목 중 계산 가능 건수 및 수신시각 범위 표시. 미조회/만료/관심 제외, 원가 미입력은 평가금액만 포함.
- [x] 별도 기본 OFF 손익 표시 capability, 현재가 응답 미변경, 추가 KIS 호출·DB migration·자동 알림 없음. 합성 Backend/Frontend 테스트 작성.
- [ ] MD05C Draft PR 최신 CI PASS 및 사용자 병합 승인.
- [ ] MD05A/B/C MiniPC 현행 버전·DB 스키마·백업·비밀파일·shared-state preflight 및 별도 배포/기능 활성화 승인.
- [ ] 실제 KIS 국내/미국 현재가·일봉 수동 조회 및 화면/참고 평가손익 인수검사. 실제 응답 시간·지연 권한 확인; 신규 토큰 승인 및 호출량 제한 유지.
- [ ] 이후 자동 시세 갱신·차트·신호·알림 단계 진행. 환율환산/세금·수수료/실현손익은 별도.
- 상세 docs/MD05C_REFERENCE_VALUATION.md.

## MD-05 운영 연동 사전점검 (2026-11-24)
- [x] PR #39 승인 병합 main@ed04fdd / CI #45309448621 SUCCESS.
- [x] MiniPC 실측: main@84e94cf clean, 3 services healthy, portfolio01/owner 1, 최신 backup 115.9h/checksum PASS/portfolio 미확인, timer disabled, KIS key metadata PASS, backend UID0, 37GB free.
- [x] 알려진 schema revision backup/restore 호환 및 optional non-root MD05 Compose overlay 작성. 실 운영 변경 없음.
- [ ] 최신 PR CI 및 병합 승인.
- [ ] 새 portfolio01 운영 백업 및 no-network 복원 검증 승인/실행.
- [ ] UID/GID·DB secret·KIS private bind 및 shared-state 사전점검, image build, rollback 준비.
- [ ] backend/frontend 배포(운영 DB schema 유지), 실제 KIS 시세/손익 별도 승인 후 인수검사.
- [ ] price history schema/자동 수집/백업 timer 재활성은 별도 검토.

## MD06A — automatic reference daily collection
- [x] MD05 operational deployment and activation PASS; actual KR/US current and reference daily reads 4/4 PASS on 2026-11-24; cached token private, rolling 24h count 5/60.
- [ ] Actual holding valuation UI test (no holdings registered; non-blocking).
- [x] Backup timer re-enabled; catch-up service activating at observation.
- [ ] Verify completed daily backup service and next scheduled run.
- [x] MD06A one-shot collector and MD06B reference-only storage core: market-local windows, 90-calendar-day request, active tracked set, durable attempt marker, shared 40/60 budget, partial-only idempotent writes.
- [ ] Latest PR CI and merge approval.
- [ ] Approved additive DB migration (production portfolio01), updated backend deployment, isolated runtime verification and actual scheduler installation/activation. No new automatic KIS calls until separately approved.
- [ ] MD06C collection status and chart read API; MD07 chart UI; signals/alerts separate, no automatic orders.

## MD06C/MD07 — stored history and chart
- [x] PR #41 merged, postmerge CI PASS, MiniPC quality02 migration and MD06 backend deploy PASS.
- [x] Backup timer daily service execution and retention PASS; postmigration quality02 backup and isolated restore PASS.
- [ ] First real KR/US collection in valid local windows, reuse cached token only; explicit live call approval.
- [x] DB-only stored reference coverage API and responsive OHLCV reference chart implementation, separate default-off display gate.
- [ ] PR CI/review/merge; deploy updated backend/frontend and approve display gate.
- [ ] MD06C scheduler installation/activation and persisted outcome status; no automatic collection currently enabled.
- [ ] Chart live browser acceptance (empty and populated states), technical indicator and signal policy separately.
