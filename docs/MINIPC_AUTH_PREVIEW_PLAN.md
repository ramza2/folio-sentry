# FolioSentry AUTH-02 — MiniPC 격리 미리보기 사전 점검

작성일: 2026-11-19 · 상태: **배포 전 읽기 전용 점검**. 모든 실행/마이그레이션/운영 변경은 별도 승인.

## 1. 현재 단계의 목적
AUTH-01은 GitHub Actions에서 단일 사용자 인증·브라우저 검증을 통과했다. 그러나 실제 개인 MiniPC에서는 Docker 버전, 남은 메모리, 기존 컨테이너, 포트 18901/18902의 점유 여부가 확인되지 않았다.

이 단계는 해당 사실을 확인할 뿐이며 다음은 **금지**한다.
- `docker compose up/down/build/pull`, 기존 컨테이너 재시작/중지·삭제, 볼륨 초기화/삭제
- `alembic upgrade`, 소유자 계정 생성, DB 포트 접근 또는 실 데이터 입력
- sudo 패키지 설치, 방화벽·라우터 변경, 새 외부 포트 오픈
- `.env`, SSH 개인키, 패스워드, GitHub PAT, DB 비밀의 출력

## 2. 기존 MiniPC에 있는 Git 저장소에서 수행 (읽기 전용 검사)
로컬 저장소 `/home/ramza/folio-sentry`는 현재 UI-01 기능 브랜치 상태였다. 아래 명령은 그 브랜치를 바꾸지 않는다.

```bash
cd /home/ramza/folio-sentry
git fetch origin docs/auth02-minipc-preflight-20261119
git show FETCH_HEAD:scripts/minipc-auth-preflight.sh > /tmp/folio-auth-preflight.sh
bash -n /tmp/folio-auth-preflight.sh
bash /tmp/folio-auth-preflight.sh /home/ramza/folio-sentry
```

결과의 `FOLIOSENTRY_MINIPC_PREFLIGHT_READONLY_COMPLETE`는 **점검 수행 완료**일 뿐, 설치/운영이 안전하거나 승인됐다는 의미가 아니다. `REVIEW_*` 항목이 있으면 원인을 확인한 후 진행.

이 스크립트는 OS/CPU/RAM/디스크, Git 브랜치/원격분류, Docker/Compose CLI·데몬 접근, FolioSentry 관련 기존 컨테이너·볼륨의 *존재 여부*, 후보 포트 18901·18902의 리스너 존재 여부만 표시한다. 외부 서버나 DB에는 접속하지 않는다.

## 3. 향후 격리 인증 미리보기 — 사전 검토용 계획 (아직 실행 불가)
사전 점검 결과와 사용자 승인이 확보될 경우 다음의 분리된 미리보기만 허용하는 방향으로 설계한다.

1. 새 Compose 프로젝트 명: `foliosentry-auth-preview`. 기존 `folio-sentry` 프로젝트, homevoice 등 다른 프로젝트 이름·볼륨·네트워크를 **재사용하지 않는다**.
2. 프로젝트 내부 별도 PostgreSQL 볼륨을 만들고 계정/자료는 모두 **합성 DEMO**만 사용. 기존 DB와 데이터 이관 금지. Docker Compose의 `-p` 사용 시 정확한 프로젝트 명 및 볼륨 생성 이름을 검사.
3. Backend/Frontend는 호스트 `127.0.0.1`에만 바인딩. 후보 18901·18902를 쓰기 전 기존 점유 확인. MiniPC의 LAN IP·0.0.0.0에 로그인용 HTTP를 공개하지 않는다.
4. 개발용 세션 쿠키 예외 `AUTH_COOKIE_SECURE=false`는 **localhost 전용 테스트**의 짧은 기간에만 사용. 허용 Origin은 `http://127.0.0.1:18902`로 제한. 실제 운영/외부접속은 HTTPS + Secure Cookie.
5. 다른 PC에서 화면을 확인한다면 SSH 터널(예: PuTTY의 127.0.0.1 로컬 포트 포워딩)을 이용해 암호화된 경로로 `http://127.0.0.1:18902`에 접속한다. 실 서비스 노출 아님.
6. 사용자가 터미널에서 비밀번호를 직접 생성한다. 초기 계정은 **로컬/독립 DB에서만** 생성하고 실제 비밀번호를 채팅/로그/명령 인자에 넣지 않는다.
7. 로그인, 로그아웃, 미인증 API 401, CSRF 거부, Figma 6개 화면, 데스크톱/모바일 표시와 오류·재시도 확인. 종료/정리 역시 격리 프로젝트 이름을 확인한 뒤 별도 명시적 승인.
8. **장기 운영은 Vite 개발 서버가 아닌 정적 프론트엔드 + HTTPS reverse proxy**로 변경한 다음 진행한다. 외부 인터넷 직접 접근을 허용하지 않는다.

## 4. 통과 조건/남은 미결사항
- MiniPC: OS, 메모리·디스크 여유, Docker Compose 접근, 포트 점유, 다른 서비스 간섭 위험 확인.
- 네트워크: 집 안에서만 사용할지, 휴대전화 외부 접속을 계획하는지; HTTPS/VPN 경로 별도 결정.
- 보안: 소유자 패스워드·계정 초기화, 장애 시 401/503 fail closed, 브라우저 세션 보존·삭제.
- 운영: 전용 백업, 리소스 상한, 이미지 버전, 롤백 방안, 지속 서비스 관리.
- PR #1→#6이 Draft인 동안 main/운영 배포와 마이그레이션 금지. 이 문서만으로 배포 승인 불가.

참고: `docs/AUTH_DESIGN.md`, `docs/AUTH_BROWSER_ACCEPTANCE.md`, `docs/DEPLOYMENT_TARGET.md`.
