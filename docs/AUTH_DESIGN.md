# AUTH-01: FolioSentry 단일 소유자 인증 설계

기준일: 2026-11-19. GitHub `main`에 인증 코드를 병합했으며, 개인 MiniPC의 운영 DB 초기화 및 서비스 공개는 별도 승인·검증 단계다.

## 왜 지금?
실제 보유 수량, 평균 매수가, 포트폴리오 평가액을 저장하기 전 로그인 보호가 선행되어야 한다.
Figma UI에서 화면만 숨기는 접근은 보안이 아니며 Backend API 접근을 별도 강제해야 한다.

## 범위
- 1인 사용자만 허용. 회원가입, 소셜 로그인, 가입 초대, 공개 페이지 없음.
- 소유자 계정은 명시적인 CLI로 **한 번만** 생성. 아이디/비밀번호는 운영 환경에서 사용자가 직접 선택. 최초 비밀번호는 **8~128자**를 허용하며 이 길이 변경은 기존 Argon2id/세션/5회 실패 잠금 규칙을 완화하지 않는다. 공개 HTTPS 접근이 예정되어 있으므로 8자 사용 시 임의의 고유한 조합을 사용하고 재사용·추측하기 쉬운 문자열을 피한다.
- Argon2id 해시를 PostgreSQL에 저장. 평문/초기 비밀번호/비밀번호를 CLI 인자로 전달하지 않음.
- opaque 세션 토큰(암호학적으로 안전한 난수) → DB에는 SHA256 digest만 저장. 8시간 절대 만료 + 30분 비활동 만료.
- HttpOnly, SameSite=Strict, Secure(기본값 true), Path=/, 호스트 범위 쿠키.
- 인증 실패 5회 시 단일 계정에 대한 15분 잠금. 실 IP별 제한은 추후 추가 필요.
- Backend가 `/api/v1/`의 모든 보호 리소스를 **기본적으로 차단**, 예외는 로그인 API 하나뿐.
- 쿠키 기반 쓰기 요청에는 같은 출처 Origin 허용목록과 CSRF 헤더 동시 검사. 로그인도 Origin 필수.
- 공용 헬스체크는 인증 정보/보유 정보를 출력하지 않으며, 자동 OpenAPI/Swagger 공개 비활성화.
- 인증이 없거나 DB 테이블·계정 준비가 안 되면 **fail closed**.
- 개인 계정 비밀번호 변경, 인증 2단계/패스키는 후속 단계(선택).

## API (AUTH-01)
- `POST /api/v1/auth/login` → `{username,password}`; 성공 시 세션 쿠키 + `{username,csrf_token,authenticated:true}`
- `GET /api/v1/auth/me` → 로그인 상태 + CSRF 토큰
- `POST /api/v1/auth/logout` → CSRF 헤더 확인 → DB 세션 삭제 + 쿠키 무효화
- `GET /api/v1/demo/overview` 포함 기존 API는 로그인 후만 조회 가능.
- 실제 Portfolio CRUD API에도 동일한 deny-by-default 미들웨어 적용.

## 배포 시 전제(추후 승인 필요)
- 최종 배포 장비: 집 MiniPC, 회사 GPU 서버 아님.
- 개발 단계의 HTTP(127.0.0.1/localhost) 테스트는 명시적인 `FOLIOSENTRY_AUTH_COOKIE_SECURE=false`와 `FOLIOSENTRY_ALLOW_HTTP_DEV=true` 조합에서만 허용.
- **실 운영은 HTTPS 필수**, 쿠키 Secure=true 유지, 개발용 우회 불허. 외부 모바일 접속은 개인 VPN(Tailscale 등) 또는 HTTPS/TLS 인증 프록시 설계 후 검증.
- `FOLIOSENTRY_AUTH_ALLOWED_ORIGINS`에 정확한 외부 HTTPS 도메인 origin만 기입; 와일드카드/CORS 모두 금지.
- 비밀번호·DB 비밀·Gateway API 키는 .env/git/log에 남기지 않고 안전한 비밀 저장 방식 사용.
- DB 스키마 적용은 승인 후 `alembic upgrade head`로 수행; 서비스 시작 시 자동 변경하지 않는다.
- 계정 bootstrap: 승인된 격리 운영 환경에서 인터랙티브로 `python -m app.auth_cli init-owner` 실행.
- 백업/복구 및 기존 서비스의 Docker/네트워크/포트 영향 별도 검증.

## 검증 게이트
1. 미인증 요청 차단: `/api/v1/demo/instruments`, `/api/v1/demo/overview`, `/api/v1/auth/me`.
2. 맞는 비밀번호만 로그인 성공; 잘못된 아이디/비밀번호는 동일한 오류.
3. 비밀번호 DB 평문 저장 없음. Argon2id 확인.
4. 세션 Cookie: HttpOnly/SameSite/Path/Secure(운영), 서버에는 토큰 hash만.
5. 무효/만료/로그아웃 세션 거부.
6. Origin/CSRF 위반 시 POST 거부.
7. DB 또는 인증 테이블 미생성 시 503 / 포트폴리오 데이터 유출 없음.
8. DB 마이그레이션은 GitHub CI 수준에서 검증하고 실제 MiniPC 적용은 미실행.
9. Frontend는 /auth/me 확인 전 기존 Figma 대시보드와 DEMO API를 읽거나 표시하지 않는다.
10. 개인 자산 실제 데이터 투입/외부 접속 전 브라우저 및 보안 인수검사 필수.

## 잔여 위험
- 단일 계정 잠금은 외부 공개 시 서비스 거부(DoS)를 유발할 수 있다. 개인 VPN/인증 프록시를 우선 적용.
- 패스키·TOTP·복구 코드와 세션/브라우저 관리 UI는 후속 단계.
- 공격자 IP별 rate-limit 및 계정 잠금 정책 조정, DB 보존·세션 정리, 휴대폰 보안 추가 검토.
- 현재 기능은 인증의 첫 단계이므로 외부 인터넷에 직접 노출하거나 실 포트폴리오를 등록하지 않는다.
