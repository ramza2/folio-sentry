# Phase 0 — 실행·점검 안내

이 브랜치는 초기 설계 PR(#1)을 기반으로 만든 **기능 골격**입니다. 운영 배포가 아니라 개발 점검만을 목적으로 합니다.

## 포함
- FastAPI: liveness, DB readiness, 두 개의 **가상 종목 메타데이터** 조회
- PostgreSQL: 준비 상태 확인 (아직 종목 데이터 테이블·마이그레이션 없음)
- React/TypeScript: API 연결과 가상 종목 목록 확인용 임시 화면
- GitHub Actions: Backend pytest, Frontend typecheck/build
- Compose: 독립 프로젝트·볼륨·네트워크, 127.0.0.1에만 바인딩

## 실행 전
- Docker와 Docker Compose 플러그인이 설치되어 있어야 합니다.
- 18901, 18902 포트가 비어 있는지 확인합니다.
- 외부 서비스·계좌 API 키는 절대 사용하지 않습니다.
- 기존 운영 서비스의 Docker 리소스를 내리거나 지우지 않습니다.

## 실행 (개발용 서버에서만)
```bash
cp .env.example .env
# .env 안 FOLIOSENTRY_DB_PASSWORD를 충분히 강한 임의 비밀번호로 변경
docker compose --env-file .env -f compose.yaml config -q
docker compose --env-file .env -f compose.yaml up -d --build

curl --fail --silent http://127.0.0.1:18901/api/health/live
curl --fail --silent http://127.0.0.1:18901/api/health/ready
curl --fail --silent http://127.0.0.1:18901/api/v1/demo/instruments
```

웹 점검 주소: `http://127.0.0.1:18902` (실행 서버 기준). 원격 PC에서는 인증된 SSH 터널을 사용합니다. VPN·리버스 프록시 없이 외부 포트 개방 금지.

## 테스트 (로컬/CI)
```bash
cd backend && python -m pip install -e ".[dev]" && python -m pytest -q
cd ../frontend && npm install && npm run typecheck && npm run build
```

## 주의
- `/api/v1/demo/instruments`는 이름/코드만 있는 가상 예시이며 실제 주가나 신호를 반환하지 않습니다.
- `/api/health/ready`에서 DB 실패 시 HTTP 503을 반환합니다.
- Compose의 DB는 별도 named volume을 사용합니다. `down -v` 실행 금지.
- 계좌 조회, 증권사 API, 매매 신호, 자동매매 및 운영 배포는 전혀 포함하지 않습니다.
- 의도적인 화면 디자인은 하지 않았습니다. Phase 1의 종목 조회/상세 API 계약 확정 후 Figma Make로 디자인하고, 그 디자인을 Frontend 구현 기준으로 삼습니다.

## 다음 검증
1. CI 결과 확인 (Phase 0 초기 CI 완료)
2. 운영 호스트의 포트 충돌·컨테이너 자원 영향 확인
3. Phase 1 용 정규화된 instrument/price_bar API 계약 작성 (Phase 1A 문서로 완료)
4. Figma Make: 대시보드/종목 목록/상세/뉴스/설정 디자인 생성 및 검토
