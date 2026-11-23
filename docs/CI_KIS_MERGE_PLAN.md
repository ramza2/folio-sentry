# OPS-CI04 — FolioSentry CI × KIS 병합 순서 및 충돌 대응 (2026-11-23)

## 현재 검증된 기준 (결과 출처: 사용자 MiniPC 실행 로그)
- 검토 브랜치 `review/ci-kis-offline-integration-20261123` 코드 스냅샷 `d2168a6c3c204a341878581036be2b30e664da26`
- `python3 -B -m unittest discover -s scripts/ci -p 'test_*.py' -v`: **38/38 PASS** (`Ran 38 tests ... OK`).
- `python3 -I -B scripts/ci/md02_md03_offline_acceptance.py`: **10/10 PASS**, `FOLIOSENTRY_MD02_MD03_STDLIB_OFFLINE_GATE_PASS`.
- PyYAML 파싱: `FOLIOSENTRY_YAML_PARSE_PASS`, 전체 `FOLIOSENTRY_CI_KIS_OFFLINE_GATE_PASS`.
- 선행 MD-03 실제 **일회용 PostgreSQL 격리 E2E PASS** (2026-11-23, `ea260ef` 검증): migration, PARTIAL DB CHECK, 멱등·충돌, SAVEPOINT 원자성, rollback 및 테스트 컨테이너 정리. 이 결합 스냅샷에서 PostgreSQL E2E 자체는 **재실행하지 않았음**.
- **실제 GitHub-hosted Actions 실행은 아직 0건**, CI job 라우팅/required checks/Runner는 미검증. 모든 PASS는 그 범위 내에서만 유효.

## 현재 GitHub 브랜치/PR 상태 (2026-11-23)
- `main`: `c156cfd9e094c747caf3f9c48ecf73eee5759699`.
- CI 최적화 `ci/usage-control-20261120`: `684309266ebbb495958352b3902acedce51f7d18`. 별도 브랜치, main 미병합.
- Draft PR #24: `88a77b2`, 최초 KIS read-only 검사 및 개인 키 파일 등록 도구.
- Draft PR #25: `b8bcbc5`, KIS 공유 상태/발급 이력 보호/호출량 제한.
- Draft PR #26: `9947c90`, MD-03 가격 후보·거래소 명시 캘린더·추가형 PostgreSQL schema/합성 E2E.
- Draft PR #27: `a8ec184`, 독립 Draft 조합 코드 리뷰용 스냅샷, **병합용 PR이 아님**.
- 통합 검토 `review/ci-kis-offline-integration-20261123`: `d2168a6`, **검토용 임시 브랜치**. main/원본 Draft PR 및 운영에는 반영하지 않는다.

## 충돌 지점과 각 원칙
1. **`.github/workflows/ci.yml` — 가장 중요**: CI 브랜치는 비용 제어용 jobs 분기, 항상 실행되는 `ci-gate`, MD03 schema 감지·합성 PostgreSQL 검사. PR #26도 기존 형태의 동일 워크플로를 수정하므로, PR #26을 원본 그대로 병합하면 CI 최적화 코드가 훼손되거나 충돌할 위험. **CI 최적화판을 기준으로 MD03 검사를 유지하는 결합 검토본의 워크플로를 최종 비교한 뒤 병합**.
2. **`AGENTS.md`, `docs/ROADMAP.md`**: CI 브랜치, PR #24/#25/#26 각각 이 파일을 수정. 브랜치 순차 반영 시 섹션 충돌/과거 체크리스트로 되돌아감 방지 필요. 검증 로그, Private 유지, 운영 승인 경계와 최신 상태를 모두 보존. 중복·구식 표현은 명시적으로 조정.
3. **KIS 서비스 코드**: PR #24는 신규 one-time probe/secret setup, PR #25는 `kis_readonly.py` 변경과 신규 `kis_shared_state.py`, PR #26은 신규 `price_*` 및 migration. CI 브랜치와 직접 코드 파일 중복 없음. PR #25의 ISSUE_MARKER 및 테스트와 PR #26의 repository begin_nested()·DB 테스트는 각각 결합 검토본과 **내용 동일** 확인.
4. **검토용 추가 테스트**: `backend/tests/test_market_data_integration.py`, 표준 라이브러리 격리 검증 및 `scripts/ci/test_ci_kis_combined_contract.py`는 독립 PR #24/#25/#26에 전부 들어간 상태가 아님. 최종 통합 PR/후속 검증 PR에서 반드시 보존 여부 확인.
5. **MD03 migration 운영 게이트**: `20261120_pricebar01`은 **운영 DB에 실행된 것이 아님**. `is_final=false`, `quality_status='PARTIAL'`, `source_observed_at IS NULL` DB CHECK 및 `analysis_eligible=False` 유지. 운영 스키마/실전 시세 표시·손익·신호는 새 승인 필요.
6. 실 KIS 토큰 및 호출량 제한: 최근 성공은 합성 transport/DB만 검증. 사용자의 과거 KIS 최초 실전 요청을 재실행하지 않음. secret 및 credential은 GitHub/로그/채팅으로 보내지 않음.

## 승인과 Actions 할당량 갱신 후 권장 순서
1. **CI 최적화부터 검토**: `ci/usage-control-20261120`에 대해 무료 사용량/비용 정책을 확인하고, 명시 승인 후 GitHub-hosted Runner에서 라우팅과 최종 Gate를 실제 검사. 현재 CI 브랜치 오프라인 28/28 PASS이지만 hosted CI 결과는 미확인. Draft 기능 병합보다 먼저 충돌을 줄인다.
2. **PR #24 개별 검토/병합**: 처음 키 설정·one-shot probe 코드와 최초 수동 조회 게이트. 필요한 변경은 main 최신으로 재동기화 후 *합성 CI*만. 운영 키 조작이나 재발급 없이 진행.
3. **PR #25 개별 검토/병합**: 최신 main 기반 재정렬, `KIS_SHARED_STATE_LOST_AFTER_ISSUE` 보수 경계 및 두 프로세스 공유 quota, 부작용 없는 기본 발급 거부를 검증. 키/상태 파일 운영 마운트 없음.
4. **PR #26 개별 검토/병합**: 최신 CI 워크플로를 덮어쓰지 않게 `.github/workflows/ci.yml` 수동 조정. 이때 `backend/migrations/env.py`와 `20261120_pricebar01`, `backend/scripts/test_price_bar_isolated_ci.py`, 캘린더 및 DB CHECK·SAVEPOINT를 보존. 합성 PostgreSQL CI 통과 필요.
5. **후속 통합 테스트 PR**: 위 단계에 포함되지 않은 `backend/tests/test_market_data_integration.py` 및 유용한 stdlib/격리 검사 계약을 별도 포팅. 원본 PR #27 또는 검토 브랜치 자체를 main에 병합하지 않는다.
6. 최종 운영 DB·배포·실 시세·손익/신호 기능은 별도 승인과 백업/격리 복원/거래소 정책 확정성 검증 전까지 금지.

## GitHub Actions 비용
- 각 원본 PR은 이미 main 대상 Draft PR로 존재한다. **브랜치에 새 커밋을 push하면 pull_request 트리거가 발생할 수 있음**. Private 저장소 월 사용량 소진 상태에서 CI 확인 없는 push는 효용이 낮고 비용 문제를 확대할 수 있다.
- 지금은 독립 PR 브랜치 rebase/merge/수정, PR 생성 또는 workflow_dispatch를 하지 않는다. 검토 코드를 현재 별도 브랜치로 보관.
- GitHub-hosted CI 8개 job 전체가 실제 성공했다는 표현 금지. 검토 브랜치의 GitHub Actions 신규 실행 0건.

## MiniPC 전원 사건
- 2026-11-23 시스템 저널의 unclean shutdown 경고가 있었으나 가족 메시지로 집 전원 스위치가 꺼졌던 사실을 확인함. **외부 전원 차단이 가장 유력한 설명**이고 코드·Docker 부하 원인은 확인되지 않음. 복구 후 foliosentry-prod 3개 컨테이너 Healthy, MD03 합성 임시 컨테이너 없음.
- 재발 방지를 위해 MiniPC 전원 멀티탭 표시·UPS 등 예방 조치를 선택적으로 검토할 수 있음.

## 완료 기준
- [x] 결합본 Python stdlib 38/38 + 합성 KIS 10/10 + YAML PASS (사용자 제공 로그, 2026-11-23)
- [x] 원본 브랜치/PR 변경 파일 비교 및 CI 워크플로/문서 충돌 지점 식별
- [x] PR #25 marker, PR #26 SAVEPOINT/테스트와 결합본 코드 동일성 확인
- [ ] 실제 hosted CI 재개 후 PR별 CI 및 안정적인 ci-gate PASS
- [ ] 사용자 명시적 병합 승인 후 CI → #24 → #25 → #26 → 통합 테스트 순서로 반영
- [ ] 운영 DB migration/키 마운트/실전 수집기 및 UI 전환은 별도 승인


## 후속 OPS-CI05 독립 3-way Git 충돌 진단
- 사용자 MiniPC에서 GitHub Private repository의 원본 6개 ref를 읽기 전용으로 가져와 오직 임시 bare repo 내부 `git merge-tree`를 7회(pairwise) 수행하도록 `scripts/ci/merge_rehearsal.py`를 별도 검토 브랜치에 준비했다.
- 원본 PR #24/#25/#26의 코드와 통합 검토본 간 핵심 23개 Git blob 동일성을 검증한다. 브랜치 SHA 불일치 또는 변경 코드 있으면 중단.
- 본 검사는 **순차 병합 시뮬레이션이 아니므로 충돌 수=0이 실제 완전 병합 승인/Actions PASS를 뜻하지 않는다**. `docs/CI_KIS_MERGE_REHEARSAL.md` 참고. MiniPC 실제 진단은 미실행.


## OPS-CI05/06 충돌 검증 업데이트
- 사용자 MiniPC에서 7쌍 pairwise merge-tree **총 13건(중복) / 고유 3개 파일** 확인: `AGENTS.md`, `docs/ROADMAP.md`, `.github/workflows/ci.yml`. CI·KIS 핵심 blob 23개 그대로 유지.
- OPS-CI06은 CI→#24→#25→#26을 실제 순서대로 임시 bare Git에서 합성 병합하여 허용 3개 파일의 충돌을 통합 검토본 기준으로 해소하는 검증 코드. 단, 중간 synthetic merge를 실제 main/PR에 사용하지 않는다. `docs/CI_KIS_SEQUENTIAL_REHEARSAL.md` 참조. 새 도구 MiniPC 실행 결과 확인 필요.


## OPS-CI06 MiniPC 1차 순차 검증 및 후속 파일 조회 버그 (2026-11-23)
- 실제 합성 순차 병합은 CI=충돌 0, #24=2, #25=2, #26=3건. 모든 충돌이 문서와 CI 워크플로 3개 파일 안에서 해소되었고 코드 23개·관리 파일 3개가 기준 브랜치와 일치함을 확인.
- **전체 최종 게이트는 FAIL**: 선택적인 후속 테스트 파일의 정상 미포함을 `git cat-file -e` 반환 코드 128 때문에 오류로 잘못 판단함.
- 후속 조회만 `git ls-tree --name-only`로 변경하고 실제 Git 임시 fixture 테스트 2개 추가. 보정된 14개 테스트/순차 최종 검사는 다시 실행해야 한다. 현재 어떤 PR도 main 병합/승인하지 않는다.


## OPS-CI07 최종 PASS 및 후속 반영 경계
- 사용자 MiniPC `ca705b0` 실행: unittest **14/14 PASS**, CI→#24→#25→#26 순차 합성 4단계 **PASS**, 충돌 0/2/2/3, 코드 blob 23/23 및 해소 파일 3/3 **MATCH**, 선택 테스트 5개 정상 미포함 확인.
- `docs/CI_KIS_FOLLOWUP_INTEGRATION_PLAN.md`에 독립 PR 병합으로는 포함되지 않는 검증 파일 5개와 후속 PR 포팅 순서 명세. **파일을 아직 main/기존 PR로 가져오지 않음**.
- 병합 전 검토는 이력상 완료했으나 실제 PR 본 병합, hosted Actions 성공, 운영 DB schema 전환/실 KIS·계좌 시세 및 운영 배포는 여전히 사용자 별도 승인이 필요. 기존 Private 정책 유지.
