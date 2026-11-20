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
- [ ] MD-02 실제 KIS Open API 신청 상태 확인 및 사용자 승인 후 제한적 최초 실 시세 GET 검증 (운영 미적용)
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



## MD-02B — KIS 최초 실 조회를 위한 일회성 운영자 점검 (2026-11-20)
- [x] 계좌 및 Open API 신청·App Key/Secret 발급 완료 사용자 확인(2026-11-20; 실전/모의 구분은 미확인)
- [x] `backend/app/kis_first_probe.py`: 기본 metadata-only 검사, 명시적인 live 승인 문자열, 최초 1회 마커, 국내/미국 각 1개 일봉 조회, 시세·토큰·원문 출력 금지
- [x] `backend/tests/test_kis_first_probe.py`: 합성 데이터/가짜 전송만, 인증정보·외부 접속 없음
- [x] KIS 신청·키 발급 완료 사용자 확인(2026-11-20; 비밀원문 미수신)
- [ ] 별도 승인 후 MiniPC에서 0600 비밀 파일 준비·메타데이터 점검
- [ ] 별도 승인 후 국내/미국 실제 **조회 전용** 호출 각 1회 검증 (현재 미실시)
- [ ] 다중 프로세스 토큰 캐시/전역 rate limit/장마감 정책 확정; MD-03 가격 저장 이전 필수
- 문서: `docs/KIS_FIRST_READONLY_PROBE.md`. **이 코드/PR은 실제 API 호출이나 운영 배포 승인이 아니다.**


## MD-02C — MiniPC 로컬 KIS 키 등록 준비 (2026-11-20)
- [x] `scripts/kis-secret-setup.py` 대화형 숨김 입력·0700 폴더/0600 파일·기존파일 덮어쓰기 방지·메타데이터 전용 check 준비
- [x] `backend/tests/test_kis_secret_setup.py` 합성/오프라인 권한 및 실패 테스트 준비
- [ ] PR #24 리뷰 및 병합 승인
- [ ] MiniPC 사용자가 `setup` + `check` 실행 후 민감정보 없는 결과만 공유
- [ ] 실전용 키 여부 확인과 **별도** 실 시세 GET 승인 후 제한 호출 검증
- 코드 준비는 운영 MiniPC 변경이나 KIS 실제 호출을 포함하지 않음.
