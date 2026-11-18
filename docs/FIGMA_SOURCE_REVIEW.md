# Figma Make 디자인 소스 검토 및 이식 계획 (2026-11-18)

## 검토 대상
사용자가 제공한 `FolioSentry 투자 모니터링.zip` (Figma Make React/Vite/Tailwind 소스). 이 파일은 GitHub에 아직 추가하지 않았다.

### 확인 결과
- 33개 ZIP 엔트리, 약 2.2MB 원본(폰트 바이너리 포함).
- `src/App.tsx`: 약 1,705라인, 6개 화면(`dashboard`, `stocks`, `detail`, `news`, `signals`, `settings`).
- `src/index.css`: 약 2,635라인. 라이트/다크 색상 토큰, 1100px/760px 반응형 분기.
- React 19 + Vite 8, Figma Make 전용 `.figma/`·Vite 플러그인·AGENTS 가 존재.
- 대시보드/내 종목/종목 상세/뉴스/신호 이력/설정, 종목 등록 모달/검색/시장 필터/테마 스위치 등 UI 코드가 들어 있다.
- API 호출(fetch/axios), 로컬 저장소 영속화, DB 연결, 실제 시세 수집은 없다.
- 컨텐츠는 고정 mock: 주가·보유량·수익률·시장 상태·기사·AI 요약·신호 모두 실제 데이터가 아니다.
- Figma ZIP의 TSX 구문 검사와 이식 CSS 문법 검사까지 확인. 환경의 패키지 다운로드 불가로 전체 빌드·브라우저 렌더링은 **아직 미검증**.

## 설계와 일치하는 점
1. 국내/미국 주식과 관심 ETF SPY, 보유 종목/관심 종목 분리.
2. 한국/미국 통화별 자산 집계, DEMO 안내(설정 화면에는 누락되어 후속 패치 필요).
3. 매수 검토/관망/위험 등 신호 타입, 이유/지표와 뉴스 표시 공간.
4. 6개 화면, 데스크톱/모바일 반응형, 라이트/다크 모드 토큰.
5. 자동 주문 UI 없이 투자 모니터링에 집중.

## 이식 전 수정 필요 (우선순위)
| 우선순위 | 이슈 | 이식 기준 |
|---|---|---|
| P0 | Figma 자체 `AGENTS.md`가 프로젝트 개발 규칙을 덮어쓸 수 있음 | **FolioSentry 원본 AGENTS.md 보존** |
| P0 | Figma 전용 `vite.config.ts`·`.figma/` 플러그인·`package.json` | 기존 React/Vite 설정 보존, 디자인 코드/CSS만 포팅 |
| P0 | mock 가격/기사/신호를 실데이터처럼 해석할 위험 | 화면별 DEMO 표기/명확한 데이터 상태/출처·기준시각 |
| P0 | 2025-02-14 등 하드코딩 시각과 현재시장 표시 | 시각·시장 상태는 백엔드 계약에 연결 전까지 명시적 데모 |
| P0 | 개인용 실제 보유정보를 정적 UI에 넣을 위험 | 정식 API 인증/접근통제 전 실데이터 사용 금지 |
| P1 | 모든 종목 클릭이 삼성전자 고정 상세화면으로 이동 | `instrument.id` 기반 선택/경로 전달 |
| P1 | 종목 등록 버튼은 모달을 닫기만 하고 저장하지 않음 | Phase 1 CRUD API와 입력 검증 연결 |
| P1 | 설정 저장/뉴스 원문 열기/기사 그룹 펼치기 등 비동작 버튼 | 미구현 표시 또는 실제 동작 구현 |
| P1 | 모든 주가·보유·시그널·뉴스가 static JS 배열 | `/api/v1/demo/overview`와 adapter를 먼저 연결하고 이후 정식 API 전환 |
| P1 | SVG 그래프는 실제 일봉/캔들 데이터 기반 아님 | OHLCV API + 차트 라이브러리로 대체 |
| P1 | 기존 Demo API fixture와 화면 mock 가격/수량/신호 수치 불일치 | 백엔드 DEMO를 단일 데이터 소스로 통일 |
| P2 | App.tsx 약 1,700줄 단일 컴포넌트 | 페이지/공통 컴포넌트/데이터 hook으로 나누기 |
| P2 | 뉴스 출처 링크 없음, AI 요약 고정 | 데이터 출처 URL과 상태 표시, Gateway는 추후 선택 기능 |
| P2 | 클릭 가능한 div와 아이콘 버튼의 키보드·aria 보완 | 접근성/반응형 인수검사 |

## 구현 순서 — 디자인 보존 / 데이터는 단계별로
1. **UI-01** 디자인 이식(별도 PR): 기존 Backend·Compose·AGENTS.md·Vite 설정 유지. App/CSS만 전환, DEMO 안내 6개 화면 필수.
2. **UI-02** 데이터 레이어: 정적 JS와 Pydantic DEMO 응답 계약을 맞추고 loading/error/stale/unavailable 처리.
3. **UI-03** 종목 선택 라우팅과 등록 모달/설정 기능 정리. DB CRUD와는 별도 검증.
4. **UI-04** Phase 1 일봉 데이터 연동, 실제 차트 교체. 지표·신호는 구현 검증 후 표시.
5. **UI-05** 뉴스 원문 링크·중복 그룹·AI 요약 연동(선택형 ModelOps Gateway), 이메일/Push 알림은 각 Phase에서.
6. 각각 독립 CI, 브라우저 인수검사 및 사용자 승인 후 병합/배포. 최종 운영 대상 집 MiniPC.

## 로컬 이식 패키지
ChatGPT 작업용으로 Figma의 화면 구조를 보존하되 `.figma/`, 플랫폼 설정, 원본 `AGENTS.md`, 폰트 바이너리를 제외한 4파일 패키지를 별도 준비했다.
- `frontend/src/App.tsx` — 원본 UI, 위험한 현재 상태 표현 및 DEMO 누락 일부 보정
- `frontend/src/style.css` — 기존 Vite에 맞춘 일반 CSS. Font system fallback
- `frontend/index.html` — 기본 한글 메타데이터
- `docs/FIGMA_IMPORT_NOTES.md` — 포팅/검증 안내

원본 ZIP 파일 자체는 이 PR에 커밋하지 않고, 코드 반영은 별도 PR로 한다.
