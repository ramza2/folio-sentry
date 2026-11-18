# FolioSentry UI-01 — Figma Make 디자인 이식

## 목적
업로드된 Figma Make React 소스의 레이아웃, 차트 일러스트, 테마/반응형 CSS와 6개 화면을 **기존 FolioSentry React/Vite 프론트엔드**에 적용한다.

## 적용 범위
- `frontend/src/App.tsx`: 6개 화면/사이드바/다크 모드/모달/필터/탭 (모두 DEMO)
- `frontend/src/style.css`: 원본 Figma CSS에서 Tailwind import와 로컬 폰트 선언을 제외한 디자인 스타일
- `frontend/index.html`: 한글 meta 및 DEMO 앱 제목
- 기존 `frontend/src/main.tsx`가 `App.tsx` 및 `style.css`를 직접 import하므로 수정 불필요
- 기존 `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `Dockerfile`, root `AGENTS.md`, Compose, Backend 유지

## 보안/정합성
- 모든 화면의 `DEMO` 경고 필수.
- 뉴스 제목/가격/지표/보유자산/뉴스 AI 설명은 **전부 허구**이며 실제 시세와 무관.
- 현재 주식별 뉴스/시세/거래소 상태가 실제로 갱신되는 것처럼 보이는 일부 표현을 DEMO로 변경.
- 종목 등록/원문 링크/전송/설정 저장 등 실제 동작이 없는 버튼은 비활성/미지원으로 표시.
- 삼성전자만 예시 종목 상세가 구현되어 NVDA/SPY에서 상세가 삼성전자 데이터로 잘못 열리지 않게 제한.
- 외부 AI/ModelOps Gateway, 시장 API, 실보유 내역, 주문 기능, DB 마이그레이션, 배포 없음.

## 남은 작업
- UI-02: Phase 1A `/api/v1/demo/overview` API 데이터 단일 소스로 통일. 로딩/실패/지연 상태 처리.
- UI-03: 선택 종목 라우팅, 다중 종목 상세, 모달 유효성 검사 및 실제 CRUD(후속 DB 승인 후).
- UI-04: 실제 OHLCV 바탕의 차트, MA/RSI/MACD 연결.
- UI-05: 국내/미국 실제 뉴스 및 허용된 ModelOps Gateway AI 설명 연결.
- 화면 분리/접근성(약 1700라인 단일 App 파일) 단계적 개선.

## 검증
- 로컬 TSX Syntax transpile 검사: PASS.
- CSS 파싱: 검사 완료.
- NPM 의존성 및 런타임 브라우저 시각 검증은 개발 환경에서 `npm install && npm run typecheck && npm run build` 후 시행.
- 외부 접속/운영 배포 없음. 테스트는 로컬 개발 클론에서만 수행.

## 로컬 적용
1. 기존 Git 클론에 다른 미커밋 변경이 없는지 확인.
2. 다운로드한 ZIP을 압축 해제.
3. `bash <압축해제경로>/apply-ui01.sh ~/folio-sentry --publish`를 실행하면, 지정한 기능 브랜치로만 이식/검증/커밋/푸시한다.
4. `--publish`를 빼면 소스만 복사하며 커밋/푸시는 하지 않는다.
5. 실제 Docker 실행, 운영 배포, DB 변경, 병합은 하지 않는다.
