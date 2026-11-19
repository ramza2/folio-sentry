# DEPLOY-01 — MiniPC 기존 Traefik + DuckDNS 연결 계획

작성: 2026-11-19 / 개발 상태: **Draft PR, 실제 배포 미실행**.

## 이미 확인한 MiniPC 사실
- 서버: `ramzaminiserver` / Ubuntu 26.04 LTS / x86_64 / 8 논리코어.
- 14GiB RAM(점검 시 약 12GiB 사용 가능), Swap 4GiB, 저장소 98GB(39GB 여유, 사용률 59%).
- Docker 29.6.2, Docker Compose 5.3.1.
- 기존 FolioSentry Docker 프로젝트/볼륨 미발견. 포트 18901,18902 리스너 없음.
- GitHub SSH remote 정상, 로컬은 `feat/ui01-figma-import-20261118` / `69fc8a0`.
- 홈 네트워크에는 **기존 Traefik + DuckDNS + ipTIME 공유기 포트포워딩** 구성 존재.
- 기존 다른 서비스의 성공 사례: `https://picknext.ramza.duckdns.org`.
- **2026-11-19 MiniPC 실측 완료**: 기존 Traefik Docker 네트워크 `proxy`, HTTPS entrypoint `websecure`, TLS certresolver `myresolver`.
- 기존 PickNext가 실제로 위 네트워크와 라우터를 사용하며, Traefik 컨테이너도 `proxy` 네트워크에 연결된 것을 읽기 전용 점검으로 확인했다.
- `https://foliosentry.ramza.duckdns.org`는 아직 **후보 주소**다. 2026-11-19 MiniPC에서 기존 PickNext와 신규 주소의 DNS IPv4 매핑이 동일함을 확인했다. **새 호스트의 TLS 인증서 발급·유효성은 미검증**이며 PickNext 성공만으로 보장되지 않는다.

## 적용할 배포 방식
별도 공개 포트 추가 없이 기존 HTTPS(443) Traefik 라우터를 재사용한다.

```text
Internet / Home LAN
   -> DuckDNS (FolioSentry FQDN, 확인 후 확정)
   -> ipTIME -> Existing Traefik :443 (기존 설정 변경 금지)
   -> frontend (Nginx production static build :8080, Docker network only)
        -> /api/* -> backend (FastAPI :8000, Docker network only)
                 -> PostgreSQL 17 (5432, Docker network only)
```

- `compose.production.yml`: FolioSentry 독립 프로젝트(`foliosentry-prod`)의 db, backend, frontend 3개만. **어떤 서비스도 호스트 ports를 공개하지 않음.** DB·Backend에는 `traefik.enable=false`.
- `compose.traefik.yml`: HTTPS를 공개하는 **frontend만** 기존 외부 Traefik Docker 네트워크에 연결. 별도 router/service 및 rate-limit 미들웨어 라벨 사용.
- `frontend/Dockerfile.prod`, `frontend/nginx.prod.conf`: Vite 개발 서버 대신 Vite 빌드 정적 파일과 Nginx /api reverse proxy 사용. 운영에서 Vite dev server 사용하지 않음.
- `backend/app/config.py`: PostgreSQL 비밀번호를 `/run/secrets/folio_db_password`에서 읽도록 확장. 실 비밀번호나 해시는 repo/.env에 기록하지 않음.
- DB secret은 최초 설정 시 사용자 전용 `~/.config/folio-sentry/pg_password`에 자동 생성(권한 600). `.env.deploy`은 비밀값 없이 도메인/Traefik 이름/파일 경로만 기록(권한 600, .gitignore 대상).
- 로그인은 기존 AUTH-01 소유자 1명, Argon2id, HttpOnly/Secure/SameSite=Strict 쿠키. 공개 Origin은 정확히 `https://<도메인>` 하나만 허용.
- RAM 상한(초기값): PostgreSQL 768MB, Backend 512MB, Frontend 192MB. 실제 모니터링 후 조정.
- LLM/ModelOps Gateway 및 실 보유 종목 입력은 이 배포 단계에 포함하지 않음.

## 실제 MiniPC에서 확인한 Traefik 기본값
```dotenv
# 운영용 설정 마법사가 Enter 입력 시 사용하는 실측 기본값
FOLIOSENTRY_TRAEFIK_NETWORK=proxy
FOLIOSENTRY_TRAEFIK_ENTRYPOINT=websecure
FOLIOSENTRY_TRAEFIK_CERTRESOLVER=myresolver
# 다음 값은 확정되지 않은 후보이므로 DNS/TLS 검증 후에만 사용
FOLIOSENTRY_DOMAIN=foliosentry.ramza.duckdns.org
```
주소 후보는 다른 서비스와 중복 사용하지 않는다. 현재 사용자의 `picknext.ramza.duckdns.org`는 그대로 유지한다.

## 스크립트 사용 (이번 단계에서 실행하지 말 것)
실제 배포는 GitHub stacked PR 병합/승인과 Traefik 설정 점검을 마친 뒤 진행한다.

```bash
# 읽기 전용: 기존 Traefik / PickNext 호환성 힌트만 표시
bash scripts/deploy.sh inspect

# 사용자 입력: FolioSentry 도메인, 기존 Traefik network/entrypoint/resolver
# Git에 기록하지 않는 로컬 .env.deploy와 개인 DB secret 최초 생성
bash scripts/deploy.sh configure

# 읽기 전용 점검: DNS 조회, 기존 네트워크, Docker Compose 검증, 외부 포트 0개
bash scripts/deploy.sh check

# 아래 2개는 실제 서비스 변경 명령! 별도 승인 전 실행 금지
# 검증된 main에서만 실행하며, 로컬 별도 DB를 신규 생성·마이그레이션·계정 초기화
bash scripts/deploy.sh db-init --confirm-new-private-db

# 신규 DB와 계정 준비 확인 후에만 HTTPS Traefik 라우트로 frontend 게시
bash scripts/deploy.sh publish --confirm-public-https
```

다른 프로젝트의 Docker 컨테이너/볼륨/설정은 변경하지 않는다. 작업 스크립트는 `git main`이 GitHub main과 정확히 일치하고 변경사항이 없는지 확인한다. DB 초기화는 **신규 빈 FolioSentry 볼륨**에서만 허용하며, 기존 프로젝트 리소스가 보이면 작업을 거부한다. 재배포/업데이트/롤백은 별도 절차와 백업 검증 전까지 이 스크립트로 처리하지 않는다.

## DuckDNS / HTTPS 확인
DuckDNS 공식 명세는 서브-서브도메인의 DNS 응답을 지원하지만 `foliosentry.ramza.duckdns.org`가 실제로 HTTPS 인증서를 발급받았다는 뜻은 아니다. 기존 PickNext URL 성공만으로 **새 hostname에 유효한 TLS 인증서가 존재한다고 추정하지 않는다**.

1. `scripts/inspect-traefik.sh`의 MiniPC 실행 결과로 `proxy`, `websecure`, `myresolver`를 **확인 완료**했다. 설정 시 이 세 값을 기본값으로 안내하되, 기존 서비스 설정 자체는 변경하지 않는다.
2. 새 hostname이 MiniPC의 공유기 공인 IP로 조회되는지 검증한다. 도메인/HTTPS 인증서는 실제 배포 전 확인한다.
3. 기존 인증서 발급 설정(HTTP-01/TLS-ALPN-01/DNS-01)과 새 도메인 사용 가능 여부를 검증하고, 공개 적용 후 인증서 SAN/발급·갱신 상태 확인한다.
4. **기존 PickNext 라우터와 Traefik 설정은 수정하지 않는다.**
5. 단일 비밀번호 보호 앱의 443 포워딩 공개는 인터넷 공격면을 만든다. 운영 전 VPN 추가 보호 또는 Traefik 인증/접근 제한, 2FA, 백업과 복구를 검토해야 한다.
6. 기존 공유기의 포트포워딩 규칙을 변경하지 않는다. DB/Backend/새 Frontend 포트를 별도로 포워딩하지 않는다.

## 실제 MiniPC에서 다음에 실행할 읽기 전용 DNS 검사

현재 **후보 도메인**은 `foliosentry.ramza.duckdns.org`이며 실사용 승인이 되지 않았다. 기존 PickNext와 후보 도메인의 DNS IPv4 응답을 비교하되 실제 IP 값은 출력하지 않는다.

```bash
cd ~/folio-sentry
git fetch origin feat/deploy01-traefik-wizard-20261119
git show FETCH_HEAD:scripts/check-duckdns-route.sh > /tmp/foliosentry-dns-check.sh
bash -n /tmp/foliosentry-dns-check.sh
bash /tmp/foliosentry-dns-check.sh foliosentry.ramza.duckdns.org
```

성공 결과의 `FOLIOSENTRY_DUCKDNS_READONLY_CHECK_PASS`는 **DNS IPv4 매핑 일치만 의미**한다. HTTPS 인증서 유효, Traefik 공개 라우터 작동, 개인계정 보안이 확보됐다는 뜻이 아니다. 미일치나 해석 실패는 `REVIEW_*`로 출력하며 공유기·DuckDNS 설정을 자동 변경하지 않는다.

## DNS 검사 실측 결과 (2026-11-19)

MiniPC에서 `scripts/check-duckdns-route.sh foliosentry.ramza.duckdns.org` 실행 결과:

```text
DNS_CHECK_MODE=READ_ONLY
DUCKDNS_IPV4_MAPPING=PASS_SAME_AS_PICKNEXT
IP_VALUES_PRINTED=NO
TLS_CERTIFICATE_VERIFIED=NO
FOLIOSENTRY_DUCKDNS_READONLY_CHECK_PASS
```

기존 PickNext와 신규 도메인의 **A 레코드 응답 일치**만 확인했다. 공유기·Traefik·인증서 발급·개인 정보 보호 수준이 검증된 것은 아니다.

## 기존 PickNext 인증서 확인 (다음 읽기 전용 단계)

```bash
cd ~/folio-sentry
git fetch origin feat/deploy01-traefik-wizard-20261119
git show FETCH_HEAD:scripts/check-existing-tls.py > /tmp/foliosentry-existing-tls-check.py
python3 /tmp/foliosentry-existing-tls-check.py --self-test
python3 /tmp/foliosentry-existing-tls-check.py
```

기존 `picknext.ramza.duckdns.org:443`에만 TLS handshake를 수행한다. 신뢰 체인, 기존 호스트명, 인증서 남은 일수, 기존 인증서 SAN이 신규 후보 도메인까지 커버하는지만 **YES/NO**로 출력하며 IP, SAN 전체, 인증서, 토큰은 출력하지 않는다.

- `PICKNEXT_TLS_TRUST_AND_HOSTNAME=PASS`는 *기존* 호스트 인증서가 정상이라는 뜻이다.
- `CANDIDATE_COVERED_BY_EXISTING_CERT=YES`라도 해당 호스트의 실제 라우터·보안·HTTPS 접속 검증은 별도 수행해야 한다.
- `CANDIDATE_COVERED_BY_EXISTING_CERT=NO`는 정상적으로 발생할 수 있다. 신규 Router가 등록된 뒤 `myresolver`로 새 인증서를 발급할 가능성이 있지만 아직 확인되지 않았다.
- LAN에서 공유기 공인 주소로 되돌아오는 hairpin NAT를 지원하지 않으면 기존 TLS 검사가 연결 오류를 낼 수 있다. 이 경우 인증서 자체 오류로 단정하지 말고 다른 승인된 네트워크에서 재검증한다.
- 실 인증서 발급/새 호스트 접속 검증은 **후보 Router 생성 이후에만** 가능할 수 있으므로, 라우터 공개 전에 미리 성공했다고 보고하지 않는다.

## 필수 승인/검증 게이트
- 저장소 PR #1~#7과 본 PR 검토, 병합 순서 확인. 실 개인용 계정·자산 데이터 투입 전 보안 테스트.
- 기존 Traefik 연결값(`proxy`/`websecure`/`myresolver`) 확인 완료, 신규 DuckDNS A 매핑 일치 확인 완료. TLS 인증서/공개 라우터/충돌 및 원격접속 보안은 아직 별도 검사해야 함.
- `docker compose config -q`, frontend production build 및 backend secret-file 테스트 PASS.
- 집 MiniPC에서 `inspect`(읽기 전용) 출력 확인 후 안전한 `configure`/`check` 수행.
- **실제 DB 마이그레이션·소유자 최초 생성·공개 HTTPS 연결은 각각 사용자의 명시적 승인** 후 진행.
- 로그인 전 API 401, login/me/logout, CSRF/Origin 거부, 백업/복원, TLS 인증서 검증, 브라우저 데스크톱/모바일 확인.
- 실 보유 종목 데이터는 인증·백업·외부 접근 제한 완료 이전에는 입력하지 않는다.
