# AUTH-01 브라우저 인수검사 — 격리 CI

2026-11-19 기준. 이 문서에 기술한 것은 **CI 환경의 가상 계정/모의 데이터 검증**이며, MiniPC 운영 서비스 배포 및 실제 사용자 로그인 검증이 아니다.

## 환경/안전
- 테스트는 GitHub Actions의 일회용 Ubuntu runner에만 실행. PostgreSQL 17 서비스 컨테이너와 loopback 서버 사용.
- 실제 집 MiniPC, 회사 GPU 서버, 실 보유 내역, 증권/뉴스 API, ModelOps Gateway API 및 운영 credential 접근 금지.
- 임시 계정 `ci-owner` 및 CI 전용 비밀번호는 검증용 가상 값. 최종 실제 비밀번호는 MiniPC에서 나중에 사용자가 직접 입력.
- 웹은 `http://127.0.0.1:18902`로만 열고, Backend `http://127.0.0.1:18091`. HTTP 비보안 쿠키 예외는 오직 테스트에만 활성화.
- 프로덕션은 HTTPS+Secure 쿠키+정확한 Origin 허용목록 필수. 로컬 HTTP 테스트 성공만으로 외부 접속 승인 불가.
- `.github/workflows/auth-browser.yml` / `frontend/e2e/auth-browser-smoke.mjs`에서 E2E 작동.
- GitHub Actions가 저장하는 스크린샷은 고정된 허구 DEMO 데이터만 포함; 7일 보관.

## 검사항목
1. 미인증 `/api/v1/demo/overview`, `/api/v1/demo/instruments`, `/auth/me` HTTP 401.
2. 로그인 페이지에 보유내역 비표시.
3. 잘못된 비밀번호 거부 및 실제 데이터 화면 불표시.
4. 정상 비밀번호 로그인 시 데모 대시보드와 경고 표시.
5. 대시보드/내 종목/종목 상세/뉴스/신호·알림/설정 6개 화면 탐색.
6. 새로고침 후 로그인 세션 유지.
7. DEMO API HTTP 503을 시뮬레이션했을 때 기존 시세 대신 오류 표시, 재시도 복구.
8. HTTP-only 세션 쿠키 확인, CSRF 누락/악성 Origin 요청 차단.
9. 로그아웃 후 서버 세션 폐기, 화면 및 DEMO API 재접근 차단, 새로고침에서도 로그인 유지 안 됨.
10. 모바일 390px 화면에서 로그인 보호 및 대시보드 확인.
11. 예기치 않은 브라우저 JS 예외 검사.

## 승인 게이트
- `CI`의 Backend/Frontend/Auth Postgres Migration/Compose 전부 PASS.
- `AUTH-01 Browser Acceptance`가 PASS. 실패 시 해당 테스트/실제 사용자 동작을 조사해 기능 PR에서 수정.
- 자동 스크린샷은 CI 아티팩트로 확인하고, 실제 배포 후 모바일/데스크톱에서 시각·접근성 인수검사 추가.
- **MiniPC에 DB 마이그레이션, 계정 초기화, Docker 실행, 외부 포트 공개를 하지 않는다.**
- PR #1→#6은 개별 검증 및 명시적 승인 후 순차적으로 main 병합.
