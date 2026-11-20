# UI-03 — 실제 보유·관심 종목 관리 화면 (운영 배포 및 읽기 전용 인수 완료)

작성: 2026-11-19. 상태 현행화: 2026-11-20. Backend 기반: Phase 1 P1 `4f184f50eaa5640a058f6d778c07ab884c88729e` (PR #16). **운영 DB는 `20261119_portfolio01` 적용 완료, Backend/Frontend `main@84e94cf` 운영 배포 PASS**, 읽기 전용 Chrome 인수검사 PASS 7 / FAIL 0 / N/A 2. **실제 CRUD E2E 및 개별 종목 행은 미검증**.

## 사용자 화면

기존 `내 종목 (DEMO)`와 구분된 사이드바 `실제 종목 관리` 메뉴. 로그인한 사용자만 접근 가능.

- 새 종목을 시장(KR/US), 거래소, 심볼, 이름, STOCK/ETF로 **직접** 등록하거나 기존 수동 카탈로그에서 선택
- `WATCH` 또는 `HOLDING` 선택, 보유 수량·평균 매입단가(문자열 10진), 메모·향후 알림 희망 여부
- 실제 등록 목록 조회·필터, 보유/관심 전환·값 수정, 삭제 확인
- 종목 검색/목록 페이지네이션, 등록 없음·로딩·연결 오류·중복·세션 만료 처리
- DEMO 시세나 보유 수치를 **실제 등록 목록에 혼합하지 않음**. 실제 시세 API 미연결: 명시적으로 `시세 없음/손익 미계산`.
- Frontend는 Fetch `credentials=same-origin` + 기존 AuthGate 세션의 CSRF 토큰; 브라우저 외부 저장소(localStorage 등)에 토큰 보관 금지
- 공급자 검증 미실시: 직접 입력한 심볼/이름은 사용자 책임이며 `MANUAL_UNVERIFIED` 표기. 브로커 계좌 연결, 주식 주문, 실제 시세 API 호출 없음.

## 구현 파일

- `frontend/src/RealPortfolioPage.tsx`: 목록/입력/수정/삭제 UI
- `frontend/src/realPortfolioApi.ts`: 응답 형식/실데이터 경계 검사, 인증 API 호출
- `frontend/src/realPortfolioApi.test.mjs`: DEMO 혼입 거부, 실패 시 가짜 숫자 fallback 없음, CSRF/Decimal 검사
- `frontend/src/App.tsx`: 신규 메뉴와 독립 화면 연결. 기존 DEMO 컴포넌트/데이터는 유지
- `frontend/src/AuthGate.tsx`: 로그인 상태의 CSRF 토큰을 내부 Context로 전달(쿠키/세션 규칙 불변)
- `frontend/src/style.css`: 접두사 `real-`의 독립 반응형 레이아웃

## 필수 검증

1. GitHub Actions의 frontend TypeScript typecheck·node tests·build PASS, Backend 인증/마이그레이션 CI PASS.
2. 운영 **별도 승인 전에는 실제 MiniPC DB 마이그레이션·Frontend/Backend 이미지 교체 금지**.
3. 운영 전 별도 안전 게이트: 기존 DB revision과 서비스 SHA 확인 → additive `20261119_portfolio01` 마이그레이션 단독 적용 → Backend API 건강·비로그인 401/403 확인 → Frontend만 업데이트.
4. 브라우저 인수검사: 로그인·신규 실 카탈로그 입력·등록/수정/삭제, 빈 상태, 보유↔관심 전환, 수량 문자열/입력 제한, 모바일 390px, 기존 DEMO 데이터 유지, 기존 PickNext 회귀 확인.
5. 개인 보유 정보는 테스트 시 **합성 종목/금액만 사용**, 실 사용자 계좌/보유 정보는 인수검사에 사용하지 않는다.
6. 자동 백업은 사용자가 `inactive`/`disabled`로 설정했으므로, 이 UI PR에서 재활성화하지 않는다.

## 후속 개발

- 국내/미국 시세 공급자 **현재 제공 범위/가격/라이선스/갱신주기 확인** 후 자동 종목 검색·시세 어댑터 설계.
- 공급자 확정 전 신뢰할 수 없는 사용자 직접 입력 종목을 `CURRENT` 또는 `STALE`로 오인하지 않는다.
- 대시보드 실 데이터 모드 연동, 실제 포트폴리오 통화별 집계, 실제 알림 발송은 각각 후속 PR.

## 운영 브라우저 인수 기록 — 2026-11-20

| 항목 | 결과 | 비고 |
| --- | --- | --- |
| 기존 로그인 및 새로고침 | PASS | 기존 세션 유지 |
| DEMO 대시보드 및 기존 메뉴 | PASS | 포트폴리오·매매 신호·뉴스 영역 |
| 신규 실제 종목 관리 화면 | PASS | 보유·관심 목록과 종목 추가 폼 |
| 전체·보유·관심 빈 목록 | PASS | 세 필터 모두 빈 상태 안내 |
| 수동 폼 KR/US 시장 선택 | PASS | KRW↔USD, 거래소 선택지 변경 후 KR 복원 |
| 실제 시세 없음·손익 미계산·DEMO 분리 | PASS | 사용자 안내 문구 확인 |
| 개별 종목 행 시세·손익 | N/A | 목록이 비어 있어 미검증 |
| Network 요청별 HTTP 상태 | N/A | 콘솔 네트워크 오류 없음, 개별 HTTP 코드는 미확인 |
| JavaScript 콘솔·390×844 모바일 화면 | PASS | 오류 0, 가로 넘침 없음, 시장 필드 접근 가능 |

검사 범위는 읽기 전용이다. 운영 데이터 등록·수정·삭제와 DB/서버 변경은 하지 않았다. 실제 종목 행 및 CRUD 검증은 별도 합성 테스트·사전 승인 후 실시한다. 서버 배포 결과와 브라우저 인수 결과를 별도로 보존한다.
