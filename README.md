# FolioSentry

국내·해외 주식/ETF를 등록하고 차트·뉴스를 모니터링하며, **규칙 기반 매매 검토 신호**를 이메일·모바일 알림으로 전달하는 **개인용** 투자 도구입니다.

> 현재 상태: 기획/설계 단계. 구현 및 실제 시세·알림 연동은 아직 시작하지 않았습니다. 투자 조언이나 자동매매를 제공하지 않습니다.

## 주요 기능(계획)
- 국내(KOSPI/KOSDAQ) 및 미국(NYSE/NASDAQ 등) 보유/관심 종목 관리
- 일봉 차트, 이동평균·RSI·MACD 등 기술적 지표
- 매수 검토 / 매도 검토 / 관망 / 위험 경고 신호와 판단 근거
- 종목별 국내·해외 최신 뉴스, 출처와 원문 링크
- 이메일 알림(MVP), Android FCM 알림(이후)
- AI 뉴스 요약·설명(이후); **AI가 매매 신호를 임의 생성하지 않음**

## 개인 인증
- 개인용 **소유자 계정 1개**. 회원가입은 제공하지 않습니다.
- Backend의 모든 `/api/v1/*` 개인 데이터 API는 로그인 전 거부합니다.
- 운영에서는 HTTPS + 안전한 HttpOnly 쿠키를 사용하며, 비밀번호는 Argon2id 해시로 저장합니다.
- 최초 소유자 비밀번호는 **8~128자**입니다. 8자를 사용한다면 다른 사이트와 겹치지 않는 무작위 조합을 권장합니다.
- 개발용 데모 UI 인증 구현은 `docs/AUTH_DESIGN.md`를 참고하세요. **현재 운영 배포·소유자 초기화는 미실행**입니다.

## 기술 방향
- Backend: Python / FastAPI / PostgreSQL
- Frontend: React / TypeScript
- Infrastructure: Docker Compose, 개인 서버
- Data: 국내·미국 시세 및 뉴스 API는 실제 이용 조건·한도 검증 후 확정

## 개발 문서
- [AGENTS.md](AGENTS.md): Cursor/개발 에이전트 작업 규칙
- [PRD](docs/PRD.md): 요구사항과 수용 기준
- [Architecture](docs/ARCHITECTURE.md): 데이터 흐름·모델·보안 원칙
- [Roadmap](docs/ROADMAP.md): 단계별 구현 및 검증 게이트

## 안전·운영 원칙
- 단일 사용자, 개인용. 자동 주문/실계좌 거래 기능 없음.
- 시세 갱신 실패, 휴장, 데이터 오류 시 신호 억제.
- API 키·계좌정보·보유내역을 저장소나 로그에 남기지 않음.
- 외부 뉴스는 기사 전체 복제보다 메타데이터 및 원문 링크 중심.

## 첫 작업
API 공급원의 실제 지원 범위·한도를 확인한 후, **모의 데이터**만 사용하는 FastAPI/React/PostgreSQL 최소 구조를 구축합니다.

## MiniPC 기존 Traefik + DuckDNS 배포 (개발 준비 단계)
- 기존 공개 서비스 사례: `https://picknext.ramza.duckdns.org`.
- 향후 `scripts/deploy.sh`가 DuckDNS 도메인, Traefik 네트워크/인증서 resolver 설정과 Docker Secret 생성을 안내합니다.
- `bash scripts/deploy.sh inspect`는 기존 Traefik 라우팅 단서를 **읽기 전용으로만** 보여줍니다.
- `configure`/`check`는 배포 없이 설정과 사전검사만, `db-init`/`publish`는 별도 명시적 승인 후 실행합니다.
- 자세한 가이드: [DEPLOY-01](docs/TRAEFIK_MINIPC_DEPLOYMENT.md).
- 현재는 Draft PR 단계이며 MiniPC의 DB·Traefik·Docker 배포는 수행하지 않았습니다.
