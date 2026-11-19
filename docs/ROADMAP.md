# FolioSentry 구현 로드맵

진행 원칙: ChatGPT에서 요구사항/설계/검증 기준을 먼저 작성하고, Cursor에는 한 작업씩 최소 프롬프트로 구현시킨다. 모든 단계는 독립 테스트를 거치며 병합/배포는 명시적 승인 후 진행한다.

## Phase 0 — 검증과 초기 구조
- [ ] 국내·해외 일봉 시세 API 자격/호출량/지연/수정주가 검증
- [ ] 국내·미국 뉴스 API 요금/약관/기사 메타데이터 검증
- [x] 최종 배포 대상으로 집의 개인 MiniPC 선정 (서버 구성/포트/인증 방법은 미확정)
- [ ] MiniPC OS/사양/기존 서비스/포트·배포 경로·접속/인증 방식 확인
- [ ] FastAPI + React + PostgreSQL 최소 골격 및 Docker Compose
- [ ] 테스트/린트/typecheck/build 기본 CI
- **게이트**: 샘플 데이터로 API/DB/Frontend 연결, 실 API 키 커밋 없음

## Phase 1A — 데이터 모델·API 계약·Figma 연계
- [x] 시장·종목·보유/관심·시세·뉴스·신호 논리 모델 설계 (`docs/DATA_MODEL.md`)
- [x] REST API 및 Decimal/시간대/가용성 계약 (`docs/API_CONTRACT.md`)
- [x] 가상 KR/US 종목·뉴스·신호 디자인 미리보기 API (`/api/v1/demo/overview`)
- [x] Figma Make 디자인 의뢰 브리프 (`docs/FIGMA_MAKE_BRIEF.md`)
- [x] Figma Make React 소스 수신·구조 검토 (`docs/FIGMA_SOURCE_REVIEW.md`)
- [x] UI-01 Figma 디자인 소스 이식 (PR #4, Draft / CI PASS)
- [x] UI-02 데모 overview API 바인딩, 로딩/오류/시세 없음 처리 (`docs/UI02_DEMO_INTEGRATION.md`)
- [ ] 6개 화면 데스크톱/모바일 브라우저 인수검사 및 디자인 사용자 확정
- [ ] UI-03 실제 보유·관심 CRUD API 연결 (독립 DB PR 필요)
- **게이트**: 모의 데이터 API 테스트·CI 성공, 실 API/DB/운영 배포 변경 없음

## AUTH-01 — 개인 전용 로그인 (실제 개인 보유 데이터보다 먼저)
- [x] 1인 소유자 계정 모델 및 Argon2id 비밀번호 해시, 인터랙티브 최초 초기화
- [x] Backend 기본 거부 인증 미들웨어 + 세션 쿠키/CSRF/Origin/로그아웃
- [x] Figma 화면 로그인 게이트, 이전 세션 재확인 및 로그아웃
- [x] 인증 테스트 및 격리 PostgreSQL Alembic 마이그레이션 CI 구성
- [ ] GitHub CI 전체 통과, 데스크톱/모바일 브라우저 로그인 인수검사
- [ ] 집 MiniPC 도메인/VPN/HTTPS 인증 접근 방식 확정
- [ ] 운영 배포·마이그레이션·소유자 초기화는 각각 명시적으로 승인받은 뒤 진행
- **게이트**: 비인증 포트폴리오 API 접근 불가, 인증 없는 개인 데이터 저장/배포 금지
- 세부: `docs/AUTH_DESIGN.md`

## Phase 1 — Watchlist와 시세
- [ ] Instrument 검색/매핑 (시장+거래소+심볼)
- [ ] 보유/관심 등록·수정·삭제
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
- [ ] 실제 MiniPC 리소스·기존 Compose 프로젝트·포트·디스크/백업 위치 확인
- [ ] 개인 전용 인증/VPN 등 외부 접속 안전 방안 확정
- [ ] Compose 리소스 격리, 환경변수·비밀관리, PostgreSQL 백업/복원 테스트
- [ ] 실제 운영 데이터 수집·알림 점검; 개인 자산/토큰 로그 유출 검사
- [ ] 필요 시 ModelOps Gateway 연결 실증 (승인·최소 데이터·장애 fallback)
- **게이트**: 배포 승인 전에는 MiniPC/회사 서버 어떤 환경에도 배포하지 않음

## 다음 Cursor 작업 (필요할 때만)
Figma Make 시안 승인 이후에만 `AGENTS.md`와 `docs/API_CONTRACT.md`를 참조하여 **확정된 단일 화면**의 UI 연결 작업을 지시한다. 별도 DB/시세 수집은 각각 독립 PR로 분리한다.
