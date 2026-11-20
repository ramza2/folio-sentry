# MD-02B — KIS 국내/미국 최초 조회 전용 점검 절차

상태: **코드·합성 테스트용. 운영/실 KIS 연결 승인 아님.** 한국투자증권 Open API 신청과 App Key/Secret 발급 완료를 2026-11-20 사용자에게 확인했다. 실전/모의 키 종류와 실제 호출 권한은 미확인. 2026-11-20 사용자는 MiniPC에서 `setup` 및 `check` 성공 마커를 확인했다. **파일 메타데이터 확인만 PASS, 키 유효성 및 실제 KIS 응답은 미검증**.

## 1. 사용자 측 선행 조건
1. [KIS 공식 이용안내](https://apiportal.koreainvestment.com/about-howto)에 따라 한국투자증권 홈페이지/앱에서 **Open API 서비스를 별도로 신청**하고 App Key/Secret 발급을 확인한다.
2. 키/시크릿/계좌번호/토큰을 채팅, GitHub, PR, 터미널 명령 인자, 로그에 복사하지 않는다. 사용자와는 **"발급 완료" 여부만** 공유한다.
3. MiniPC 실행 사용자가 소유하고 다른 계정이 읽을 수 없는 일반 파일 2개(0600)를 별도 위치에 준비한다. 예: `$HOME/.config/folio-sentry/kis_appkey`, `kis_appsecret`. 둘은 서로 다른 파일이어야 하며 symlink 금지.
4. 첫 호출은 별도 사용자 승인·운영 영향 점검 이후에만 실시한다. 코드가 GitHub에 있더라도 운영 컨테이너에 설치되었다고 가정하지 않는다.

## 2. 메타데이터 점검만 (네트워크·비밀 원문 읽기 없음)
Backend Python 환경에서 실행한다. **아직 키 발급 전이면 실행하지 않는다.**

```bash
python -m app.kis_first_probe check \
  --appkey-file "$HOME/.config/folio-sentry/kis_appkey" \
  --appsecret-file "$HOME/.config/folio-sentry/kis_appsecret"
```

성공: `KIS_PRIVATE_FILES_METADATA_PASS_NO_SECRETS_READ_NO_NETWORK`. 이것은 파일 소유권·유형·권한·크기 검사일 뿐, 키 유효성/조회 권한/시세 품질 검증이 **아니다**.

## 2A. MiniPC 안전 키 등록 — 2026-11-20 (실 API 호출 없음)

한국투자증권 Open API 신청·App Key / App Secret 발급 완료를 사용자가 확인했다. **사용자가 실전투자용 키를 확인했다(2026-11-20).** MD-02 클라이언트는 실전 API 호스트에 고정되어 있으므로 실전용 키인지 먼저 사용자 화면에서 확인한다. 키를 채팅이나 GitHub에 공유하지 않는다.

이 PR이 리뷰 및 병합된 후에만, 사용자가 **MiniPC 일반 계정 대화형 SSH 터미널**에서 다음을 실행한다. 스크립트는 표준 라이브러리 전용이며 서버 API, DB, Docker, Traefik, KIS 외부 네트워크를 사용하지 않는다.

```bash
cd ~/folio-sentry
python3 scripts/kis-secret-setup.py setup
python3 scripts/kis-secret-setup.py check
```

키는 명령 인자가 아닌 **숨김 입력(getpass)** 두 번으로 받는다. 터미널 기록·화면공유·세션녹화는 피한다. `$HOME/.config/folio-sentry/` 폴더(0700)와 `kis_appkey` / `kis_appsecret` 파일(각 0600)만 만들며, 기존 파일 덮어쓰기/심볼릭 링크/다른 사용자 권한을 거절한다. `sudo`, `cat`, `echo`, 명령 인자, 환경변수, Git, 로그에 키를 입력하지 않는다.

출력 마커: `FOLIOSENTRY_KIS_SECRET_SETUP_LOCAL_PASS_NO_NETWORK`, `FOLIOSENTRY_KIS_SECRET_METADATA_PASS_NO_CONTENT_READ_NO_NETWORK`. 검사 명령은 파일 원문을 열지 않고 타입/소유권/권한/크기만 확인한다. 이 마커들은 실제 KIS 키 유효성이나 시세 API 성공을 의미하지 않는다.

오류 발생 시 오류 코드만 공유한다. 비밀파일의 홈 백업·스냅샷은 접근을 제한하고 암호화 정책을 확인한다. **이 단계에서 운영 Compose에 비밀파일을 마운트하지 않는다.**

## 3. 최초 실 조회 (2026-11-20 사용자 승인으로 1회 실행 완료 — 재실행 금지)
승인 뒤 지정한 국내·미국 각 1거래일을 **원주가(RAW) 조회만** 한다. 고정 대상은 예시 종목 `KR/XKRX/005930`, `US/XNAS/AAPL`이며 수량·평균단가·계좌번호를 전달하지 않는다. 명시적인 승인 문자열 `APPROVE_KIS_ONE_TIME_READONLY_QUOTES` 없이는 호출할 수 없다. 실행할 때 날짜는 **실제 두 시장에서 해당하는 과거 거래일**로 각각 지정해야 한다. 과거 1거래일의 일봉 API 반환도 확정 정산가격으로 간주할 수 없다.

실제 호출 순서는 **OAuth 토큰 POST 1회 + 국내 일봉 GET 1회 + 1.1초 간격 + 해외 일봉 GET 1회**다. 재시도·추가 조회·주문·계좌조회·DB 기록·UI 반영 모두 없다. 호출 직전에 `~/.local/state/folio-sentry/kis-first-readonly-probe.attempted` 일회성 잠금 마커를 기록하여 동일 MiniPC 사용자 재실행을 차단한다. 네트워크 오류나 빈 결과로 실패해도 자동 재실행 금지. 다른 실행계정·서버·프로세스의 KIS 토큰/레이트리밋을 이 마커가 보호하지는 못한다.

시세 값·비밀정보·응답 본문은 출력하지 않고, 국내·미국별 비확정 OHLCV 행 건수 및 성공/실패 코드만 출력한다. 어느 시장이든 0건이면 미확인 처리. 응답 구조가 정상이어도 `is_final=False`이고 신호·잔고·차트에 사용 불가.

**운영 상태**: 사용자 승인으로 실전 KIS 최초 조회 1회 완료(토큰 POST 1회, 일봉 KR/US 각 GET 1회). DB/서비스/Compose/Frontend/백업/Traefik은 불변. 별도 실호출 추가 승인 전 재실행 금지.

## 4. 후속 게이트
- 실 응답 형태·해외 거래소 코드·조회 범위·지연·원주가/수정주가·휴장 및 1일 최종성 검증
- 단일 인스턴스 이외의 토큰 공유 및 전역 호출량 제한/감사, 안전한 오류 처리를 마련한 뒤 스케줄링 설계
- price_bar 저장/멱등·검증, MiniPC DB migration, 운영 배포와 UI 연동은 모두 별도 승인


## 2026-11-20 실제 KIS 최초 조회 인수 결과 — 사용자 제공 MiniPC 실행 로그
- 승인: 한국투자증권 **실전투자용** App Key/Secret, 조회 전용 3회(OAuth 토큰 POST 1회, 삼성전자 일봉 GET 1회, 애플 일봉 GET 1회). 사용자 명시 승인.
- GitHub PR #24 검증 커밋 `01703f507cde8010b99c217ffbf1ae5eb3fccc3a`의 도구를 임시 폴더에서 실행. main 배포·작업트리·DB·Compose 변경 없음.
- `KIS_PRIVATE_FILES_METADATA_PASS_NO_SECRETS_READ_NO_NETWORK`
- `KIS_KR_UNFINALIZED_BAR_COUNT=1`, `KIS_US_UNFINALIZED_BAR_COUNT=1`
- `KIS_FIRST_CALL_STATUS=READONLY_QUOTE_SHAPE_PASS_NOT_PRODUCTION_APPROVAL`, `FOLIOSENTRY_KIS_FIRST_READONLY_PASS`
- 대상 조회 거래일: 국내·미국 **2026-11-19**, RAW 가격. KIS 실제 OAuth 발급에 대한 한국투자증권 카카오톡 알림 사용자 수신.
- **성공 판정 범위는 접근 토큰 발급 및 국내/미국 일봉 응답 구조·정규화 성공뿐**. 실제 가격값·장마감 최종성·원주가/수정주가 정합성·실시간 지연·공급자 관측시각·장기조회는 아직 미검증. `is_final=False`, `source_observed_at=None` 유지.
- KIS 안내 메시지: 토큰 발급 시점부터 유효기간 **24시간**, **1일 1회 발급 원칙**, 잦은 추가 발급 시 이용 제한 가능. **재발급을 위한 probe 재실행 및 1회 마커 삭제 금지**.
- 후속: 실제 재호출 없이 합성 fixture로 전역 레이트리밋 및 다중 프로세스 토큰 공유·재기동 정책 설계. 본 PR은 여전히 미병합 Draft이며 시세 적재/운영 표시/주문 기능 없음.
