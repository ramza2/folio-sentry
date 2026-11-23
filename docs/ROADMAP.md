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
- [x] MD-02 KIS Open API 신청/실전 키 발급 후 최초 토큰 POST·KR/US 일봉 GET 각 1회 사용자 검증 PASS (2026-11-20, 기존 Draft PR에 별도 기록, 운영 미연동)
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


## MD-03 — 일봉 시세 품질·격리 저장 경계 (2026-11-20)
- [x] KRX/미국 거래소 시간대 및 보수적 장마감+2h 제한, 미국 DST·미래/주말·결측/오래된 시세 품질검사 오프라인 코드 작성. 확정 거래일/종가 인정은 미구현
- [x] `price_bar` SQLAlchemy 모델 + 추가형 `20261120_pricebar01` migration 코드 작성 (기존 표/행 불변, 최종시세 DB CHECK 차단)
- [x] 멱등 단일 거래세션 INSERT: 동일 시세 NOOP, 다른 시세 충돌 발생, 불확정 PARTIAL 고정, 실제 신호/UI 노출 금지
- [x] 합성 PostgreSQL CI 격리 migration 및 롤백 테스트 코드 준비 (전용 `folio_ci`만 허용)
- [x] MD-03 GitHub Actions CI 6/6 PASS 및 격리 PostgreSQL 마이그레이션·멱등·DB 확정시세 차단·롤백 검증 완료 (2026-11-20)
- [ ] MD-03 코드 리뷰와 병합 승인
- [ ] PR #24/#25 병합 게이트와 후속 통합 검토 (현재 둘 다 Draft/미병합)
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


## MD-02~03 임시 통합 CI 게이트
- [x] PR #24 최초 조회/로컬 키 관리, #25 공유 토큰, #26 비확정 price_bar 세 기능 간 충돌 점검용 소스 조합 작성
- [ ] 단일 통합 GitHub CI 전체 PASS
- [ ] 개별 PR 리뷰/명시적 병합 승인 전 main/운영에 반영 금지


## 통합 리뷰 보완/게이트 (2026-11-20)
- [x] PR #25 캐시 상태 파일 유실 후 기존 토큰 발급 기록 보호: 독립 영속 마커 + 실 키 없는 합성 회귀 테스트
- [x] PR #26 중간 가격 충돌 시 한 배치 부분 INSERT 방지: 내부 SAVEPOINT + PostgreSQL 격리 테스트
- [ ] PR #27 수정본 통합 CI 6/6 최종 확인
- [ ] PR #24→#25→#26 개별 리뷰·병합 승인. AGENTS/ROADMAP 문서 충돌 조정 필요
- [ ] 공식 거래소 전체 캘린더·가격 확정 정책 검증, 실 API/KIS/운영 DB/배포 별도 승인


## MD02-MD03-STD01 — 합성 KIS→시세 게이트 독립 로컬 테스트 (2026-11-20)
- [x] PR #27 통합 Draft를 기준으로 독립 오프라인 리뷰 브랜치 생성, 기존 PR #24/#25/#26·main 불변
- [x] Python stdlib 10개 단위 테스트 소스 작성: LIVE 기본 거부, 합성 토큰·국내/미국 일봉·PARTIAL, 공유 할당량, 실패 시 예약, 캘린더 보수 정책, price_bar 저장/마이그레이션 계약
- [x] 사용자 MiniPC `git archive` 격리 임시 폴더에서 stdlib 테스트 10/10 PASS (2026-11-23)
- [ ] 정상 GitHub Actions 갱신 후 PR #24→#25→#26 및 CI 최적화 브랜치의 결합 검증
- [x] Private 유지, 실 KIS 호출/실 DB/Docker/운영 배포/시세 UI 연동 금지 유지
- 자세한 계획·한계: `docs/MD02_MD03_STDLIB_OFFLINE_GATE.md`

 
## MD03-DB-LOCAL — MiniPC 완전 격리 PostgreSQL 저장 E2E (2026-11-23)
- [x] MD02/MD03 합성 KIS·PARTIAL 연동 stdlib 검사 10/10 PASS (사용자 MiniPC 실행 결과 확인)
- [x] 임시 합성 PostgreSQL 컨테이너의 --network none, tmpfs 저장소, 포트 없음 및 운영 image ID 재사용 설계
- [x] 운영 Backend/DB 컨테이너는 image ID만 읽고 새 Python+PostgreSQL 테스트 컨테이너만 사용하도록 분리, 사전점검/명시적 확인 문자열/자동 정리 코드 작성
- [x] 일회용 DB에 Alembic 20261120_pricebar01 및 저장 멱등·충돌·원자성·finality CHECK·롤백 검증 연결
- [x] Docker 무실행 정적 검사 및 문서 초안 작성
- [x] MiniPC 격리 archive에서 Bash 구문·Python 계약 6/6·Docker preflight PASS (2026-11-23)
- [x] 격리 PostgreSQL E2E PASS (2026-11-23, 합성 데이터만)
- [ ] GitHub Actions CI 최종 검증·기존 Draft PR 단계적 병합은 무료 사용량 갱신/사용자 별도 승인 뒤 수행
- [x] Private 유지, 실 KIS 토큰 재발급/운영 마이그레이션·서비스 변경 없음

## MD03-DB-LOCAL-2 — 아카이브 Python import 검증 (2026-11-23)
- [x] 첫 실행: Bash 구문 PASS, Docker 안전계약 5/5 PASS, 일회용 PostgreSQL READY.
- [x] 첫 DB E2E는 ModuleNotFoundError: No module named 'app.market_data'로 중단. 미완료/FAIL을 기록.
- [x] PYTHONPATH=/workspace/backend 고정 및 python -m scripts.test_price_bar_isolated_ci 실행으로 임시 아카이브 소스를 우선 검색하게 수정.
- [x] Alembic 전에 실제 app 모듈 import 경로 확인. 이전 운영 이미지의 설치 패키지가 검색되면 fail-closed.
- [x] 수정 커밋 MiniPC Bash 구문·안전계약 6/6·일회용 PostgreSQL E2E PASS (2026-11-23)
- [x] 이전 실패의 임시 Docker 컨테이너 잔존 없음 (읽기 전용 조회)
- [x] Private 유지, main 병합/운영 DB/실 KIS 재호출 없음.


## MD03-DB-LOCAL-3 — MiniPC 최종 격리 E2E 완료 (2026-11-23)
- [x] 수정 커밋 ea260ef 테스트: Bash 구문 PASS, 안전계약 **6/6 PASS**, Docker 운영 이미지 읽기 전용 사전검사 PASS
- [x] 임시 PostgreSQL 기동 및 마운트된 아카이브 import PASS
- [x] SAVEPOINT 배치 원자성, 중복 저장·가격 충돌 차단, is_final/quality DB CHECK, ROLLBACK, Alembic 20261120_pricebar01, 남은 가격 행 0건 모두 PASS
- [x] FOLIOSENTRY_MD03_ISOLATED_POSTGRES_INTEGRATION_PASS / FOLIOSENTRY_MD03_LOCAL_E2E_COMPLETE 사용자 로그 확인
- [x] 이전/현재 일회용 Docker 컨테이너 라벨 조회 0건. 운영 이미지 ID 조회 외의 운영 서비스 접근 없음
- [ ] MiniPC 이전 전원 종료·재부팅 의심 현상: 부팅 이력/커널 OOM/thermal/watchdog/하드웨어 및 운영 서비스 건강 상태를 **읽기 전용** 조사, 원인 미확인
- [ ] 시스템 안정성 확인 전 추가 Docker 부하/운영 배포·DB 마이그레이션 보류
- [ ] GitHub hosted Actions 최종 검증과 Draft PR 단계적 병합은 별도. Private 유지


## OPS-STABILITY-01 — MiniPC 비예정 재부팅 분석 (2026-11-23)
- [x] MiniPC 부팅 이력 확인: 이전 journal 09:52:19 종료, 새 부팅 11:24:21 KST. 중간 시간대 원인 불명
- [x] 현재 RAM 14GiB/가용 12GiB, Swap 0B; 운영 Frontend/Backend/PostgreSQL 컨테이너 **healthy** 3개 (상태 조회 기준)
- [x] 이전 부팅 커널 경고 검색에서 해당 사건 직전 명시적 OOM/Kernel Panic 확인되지 않음. 발견된 NMI watchdog/TSC 초기화 기록은 **11월 1일**, 사건 관련 증거 아님
- [x] 일회용 MD03 라벨 Docker 컨테이너 잔존 0건. `last` 명령은 미설치이므로 설치하지 않고 journalctl로 확인
- [ ] 사건 전후 2026-11-23 09:40~09:55 이전 부팅 journal의 shutdown/OOM/thermal/watchdog/I-O 관련 로그 읽기 전용 확인
- [ ] 예상치 못한 shutdown·전원 문제의 재발 여부 관찰; 필요하면 BIOS/전원/시스템 로그를 별도 검토
- [ ] 시스템 안정성 확보 전 추가 격리 Docker 부하 테스트/운영 DB 마이그레이션/운영 배포 보류


## OPS-STABILITY-01 후속 로그 확인 (2026-11-23)
- [x] 이전 부팅 09:40~09:55 KST shutdown/OOM/kernel panic/thermal/watchdog/I/O error 키워드 검사에서 해당 패턴 로그 미검출(로그 없다는 의미 아님)
- [x] 현재 부팅 11:24:26 KST `systemd-journald: system.journal corrupted or uncleanly shut down, renaming and replacing` 확인 — **이전 저널 비정상 종료/손상 정황**
- [ ] 정확한 원인 미확정: 정전/전원 어댑터/강제 리셋/시스템 멈춤/저널 손상 등 감별. OS 비정상 종료와 Docker E2E의 인과관계 증거 없음
- [ ] 이전 저널 마지막 메시지·정상 shutdown 시퀀스, 현재 저장장치 오류·시스템 부팅 상태 읽기 전용 추가 검토(로그에 비밀 노출 주의)
- [ ] 안정성 확인 전 부하가 있는 Docker E2E, 운영 DB schema 변경/배포 중단. Private 유지


## OPS-CI03 — CI 최적화·KIS MD02/03 결합 검토 (2026-11-23)
- [x] CI 단독 브랜치 12개 변경 경로, KIS 검토 브랜치 29개 변경 경로 및 공통 충돌 후보 `.github/workflows/ci.yml`, `AGENTS.md`, ROADMAP 확인
- [x] 검토 소스 기반 신규 `review/ci-kis-offline-integration-20261123` 생성, CI 브랜치 파일만 선별해 결합
- [x] 6개 선택 검사와 stable final gate 유지, MD03 price_bar PostgreSQL 분리 검사 유지 및 KIS 순수 stdlib 10개 검사 자동 추가
- [x] 신규 통합 정적 계약 4개 작성. MiniPC 통합 unittest **38/38 PASS**, 합성 KIS **10/10 PASS** (2026-11-23)
- [x] MiniPC 격리 임시 archive에서 stdlib **38/38**, KIS 합성 **10/10**, YAML 파싱 **PASS**, 최종 FOLIOSENTRY_CI_KIS_OFFLINE_GATE_PASS
- [ ] 할당량 회복 후 GitHub-hosted Actions 실제 CI 라우팅/스킵/6개 선택 job/MD03 migration 및 final gate 검증
- [ ] 사용자 명시적 승인 뒤 적절한 순서로 CI 브랜치 및 PR #24/#25/#26 병합; PR #27은 검토 Draft일 뿐 병합 대상 아님
- [x] Private 유지, KIS 자동 수집/운영 DB/시세 UI/배포 변경 없음
- 참고 `docs/CI_KIS_COMBINED_REVIEW.md`

## OPS-STABILITY-01 전원 차단 정황 보완 (2026-11-23)
- [x] 가족 연락에서 집 전원 스위치가 꺼진 것을 확인하고 전원을 다시 켰다는 정보 확보 → 비정상 저널 종료 및 재부팅 시간대와 부합, 외부 전원 차단이 가장 유력
- [x] 복구 후 운영 Frontend/Backend/DB Healthy, 일회용 테스트 Docker 잔존 없음
- [ ] 가정 전원 스위치가 재차 내려가지 않도록 물리적 표식/전원 케이블 고정/필요하면 UPS 별도 검토. Docker 또는 앱 장애 단정 금지


## OPS-CI04 — 병합 계획 작성 (2026-11-23)
- [x] PR #24/#25/#26/#27 독립 Draft와 CI 최적화 브랜치 변경 파일 확인, 충돌 후보 구분
- [x] PR #25 공유 토큰 상태 복구 마커, PR #26 가격 SAVEPOINT 및 DB 테스트가 결합본과 동일한지 확인
- [x] 병합 순서/필수 게이트 문서 `docs/CI_KIS_MERGE_PLAN.md` 작성 (실 병합 아님)
- [ ] Actions 무료 할당량 갱신과 사용자의 별도 승인을 전제로 CI → PR #24 → #25 → #26 → 통합 회귀 테스트 순으로 추진
- [x] FolioSentry Private 유지, 실 KIS 호출/운영 DB 및 MiniPC 변경 없음


## OPS-CI05 — GitHub Actions 없이 PR 병합 충돌 실사 준비 (2026-11-23)
- [x] main·CI·Draft PR #24/#25/#26 및 통합 검토 기준의 고정 SHA와 Private repo 상태 확인
- [x] 임시 bare Git 저장소에서만 read-only fetch 및 `merge-tree`로 7개 독립 pairwise 충돌을 진단하는 stdlib 스크립트 작성
- [x] 중요 CI/KIS/MD03 핵심 23개 코드 blob이 통합 검토본과 동일한지 확인하는 보수적 검사 작성
- [x] 별도 무통신/unittest 계약 테스트 6개·실행 가이드 문서 작성
- [ ] MiniPC GitHub 읽기 전용 fetch 통한 최신 SHA 검증·pairwise 실제 충돌 파일 목록 수집, 로컬 unittest PASS 결과 확인
- [ ] 충돌이 있는 경우 **별도 검토 브랜치**에서 해결책 준비하고 최종 CI 통합 검증 반복 (main·기존 PR 미변경)
- [ ] hosted Actions 계정 할당량 갱신과 사용자의 별도 승인 후 단계적 main 병합 실행
- [x] Private 유지, 실 KIS 호출/토큰 재발급·운영 DB/컨테이너 변경 금지
- 상세 `docs/CI_KIS_MERGE_REHEARSAL.md`


## OPS-CI06 — 7개 pairwise 충돌 실사 후 실제 순차 병합 검증 (2026-11-23)
- [x] MiniPC에서 7쌍 독립 merge-tree 완료: 합산 충돌 13건, 고유 충돌 파일 3개(AGENTS, ROADMAP, CI workflow)
- [x] 사용자 Git source 폴더는 읽기만 하고 임시 bare Git에서 CI→#24→#25→#26 4단계를 합성 병합하는 검토 도구 구현
- [x] 허용 충돌 3개 파일은 기존 검증된 통합본 blob만 선택하며 그 외 모든 충돌 차단. 최종 23개 코드 blob·3개 해소 파일 동일성 비교
- [x] 오프라인 Git fixture 계약 unittest 6개와 사용 설명 작성
- [x] MiniPC 기존 6개+신규 6개 unittest **12/12 PASS**, 순차 merge 0/2/2/3 충돌을 허용 3개 파일 blob으로 해소, 코드 23/23·관리 파일 3/3 MATCH 확인 (단 최종 follow-up 조회 FAIL)
- [ ] 이후 실제 PR 병합 각 중간 단계의 AGENTS/ROADMAP CI 기여를 보존하도록 재검토. 합성 문서 선반영 상태를 실제 main에 재사용 금지
- [ ] GitHub-hosted Actions 무료 할당량 갱신과 사용자 별도 승인 뒤 단계적 병합
- [x] Private 유지, 운영 MiniPC/실 KIS/운영 DB 불변
- 상세 `docs/CI_KIS_SEQUENTIAL_REHEARSAL.md`


## OPS-CI06-FIX — 후속 검증 파일 조회 false FAIL 보정 (2026-11-23)
- [x] 사용자 MiniPC 순차 rehearsal: 12/12 unittest PASS, refs PASS, CI→#24→#25→#26 4단계 완료, 충돌 0/2/2/3, 코드 23/23 및 관리 파일 3/3 MATCH
- [x] 마지막 `SEQUENTIAL_FOLLOWUP_CHECK_FAILED`는 없는 파일의 `git cat-file -e`가 128을 반환하는 데 스크립트가 1만 정상 미포함으로 허용했던 버그라고 진단
- [x] `git ls-tree --name-only` 기반 정상 미포함 검사로 교체; 임시 Git 실제 fixture / 비정상 쿼리 응답 차단 **테스트 2개 추가**
- [ ] MiniPC 신규 14개 unittest 및 전체 합성 순차 병합 최종 PASS 마커 재확인
- [ ] 후속 독립 통합 검증 파일의 포팅 순서·최종 Actions gate 재검증은 별도; main·PR 실제 병합 아님
- [x] Private 유지, 실제 KIS 호출/키 관리/운영 DB/Docker/배포 및 원본 PR/CI 브랜치 변경 없음
