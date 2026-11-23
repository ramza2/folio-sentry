# OPS-CI05 — PR #24/#25/#26 사전 병합 충돌 진단 (2026-11-23)

## 목적
Actions 무료 할당량을 추가 소비하지 않고, Private 저장소 FolioSentry의 **현행 CI 최적화**와 KIS Draft PR #24/#25/#26 사이의 실제 Git 3-way merge 충돌 파일을 확인한다. `main`, 기존 PR, 운영 MiniPC 서비스는 변경하지 않는다.

이 검사는 **각 브랜치 쌍을 독립적으로 병합한 결과(pairwise)**를 보여준다. `CI → #24 → #25 → #26`의 순차 병합 완성이나 충돌 해결을 증명하지 않는다. 충돌이 출력되면 GitHub에서 실제 수정/병합 전 추가 검토가 필요하다.

## 안전 경계
- 소스 코드: `scripts/ci/merge_rehearsal.py`, 계약 테스트 `scripts/ci/test_merge_rehearsal.py`.
- GitHub 저장소의 메인 ref/브랜치와 검토 중인 6개 ref를 각각 **정확한 40자리 SHA**로 검증. 변경되면 fail closed로 재검토.
- 읽기 전용 `git remote get-url origin` 대상은 Private `ramza2/folio-sentry`의 승인된 GitHub SSH/HTTPS URL만 허용. URL에 포함된 토큰이나 다른 호스트/저장소는 거부.
- `--preflight`는 원본 저장소의 remote·Git 버전만 읽는다. **fetch 없음**.
- `--run`은 `tempfile.TemporaryDirectory` 안에서만 `git init --bare`, GitHub private branch **fetch(다운로드만)**, SHA 및 코드 blob 확인, `git merge-tree --write-tree --name-only`를 실행한다.
- `git merge-tree --write-tree`는 **임시 bare repo에만 Git 객체를 생성**하며 실제 병합 커밋/checkout/main 브랜치 변경을 하지 않는다. GitHub에 push하지 않는다.
- KIS 실 API/토큰·계좌, PostgreSQL, Docker, 운영 DB/서비스, 호스티드 GitHub Actions와 무관.
- 충돌 경로의 **파일명만** 출력한다. 변경 파일 내용·비밀값·실제 토큰을 출력하지 않는다.
- 기존 PR 및 GitHub-hosted Actions 상태는 변함없다. 새 검토용 브랜치는 PR을 열지 않는다.

## SHA 고정
| 역할 | GitHub 브랜치 | 검증 SHA |
|---|---|---|
| Main | main | `c156cfd9e094c747caf3f9c48ecf73eee5759699` |
| CI | ci/usage-control-20261120 | `684309266ebbb495958352b3902acedce51f7d18` |
| #24 | feat/md02b-kis-first-readonly-probe-20261120 | `88a77b27990c7f23bc0a26917a0c99090fb2776d` |
| #25 | feat/md02d-kis-shared-token-quota-20261120 | `b8bcbc5bd23613fcecf1117df7e0443fa729d550` |
| #26 | feat/md03-price-bar-additive-offline-20261120 | `9947c90bc5801f42db2891961c95ffbd3e96398a` |
| 통합 검토 기준 | review/ci-kis-offline-integration-20261123 | `0c1c22ada265a3607d0436f7b138b79356cf7f56` |

이 브랜치 `review/ci-kis-merge-rehearsal-20261123`는 **통합 기준 브랜치의 이미 검증된 SHA에서 따로 분기**했으므로, source-ref 자체는 변경하지 않는다.

## 검사 내역
1. `main + CI`, `CI + PR #24`, `CI + PR #25`, `CI + PR #26`, `#24 + #25`, `#24 + #26`, `#25 + #26`의 **7개 독립 pairwise 충돌 파일/개수** 수집.
2. PR #24의 probe·키 설정 테스트, PR #25의 공유 token/limit 핵심 코드, PR #26의 price_bar·migration·SAVEPOINT, CI router/gate 핵심 코드 등 **23개 Git blob**가 통합 검토본에 그대로 보존되었는지 바이트 수준 SHA 비교.
3. 코드 blob이 달라졌거나 원본 PR HEAD SHA가 움직였으면 즉시 중단한다. 이 경우 기존 PASS를 현행 결과로 확대 해석하지 않는다.
4. 최종 `FOLIOSENTRY_MERGE_REHEARSAL_REVIEW_COMPLETE_NOT_MERGE_APPROVAL` 마커는 **진단 완료**만 의미한다. 충돌이 0건이라는 의미도, 병합 승인이 난다는 의미도 아니다.

## MiniPC 실행 (오프라인 테스트 + GitHub 읽기 전용 fetch)
해당 브랜치 SHA를 GitHub에서 확인한 후 아래 절차를 실행한다. 이 구문은 README용 템플릿이므로 실제 호출 시에는 확인한 커밋 SHA로 TARGET을 치환한다.

```bash
cd ~/folio-sentry
BRANCH="review/ci-kis-merge-rehearsal-20261123"
TARGET="<GitHub에 반영된 이 브랜치의 검증된 HEAD SHA>"

git fetch --no-tags origin "refs/heads/$BRANCH"
test "$(git rev-parse FETCH_HEAD)" = "$TARGET" || exit 1

TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
git archive "$TARGET" scripts/ci/merge_rehearsal.py scripts/ci/test_merge_rehearsal.py | tar -x -C "$TMP"

PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover \
  -s "$TMP/scripts/ci" -p 'test_merge_rehearsal.py' -v

python3 -B "$TMP/scripts/ci/merge_rehearsal.py" --preflight
python3 -B "$TMP/scripts/ci/merge_rehearsal.py" --run
```

`--run`은 GitHub 인증이 필요한 **조회 전용 fetch**를 포함하므로, 네트워크 사용을 전혀 원치 않으면 `--preflight`까지만 수행한다.

## 선행 검증과 미완료
- 통합 검토 브랜치 기준 사용자 MiniPC에서 CI stdlib **38/38 PASS**, KIS 합성 **10/10 PASS**, YAML 파싱 PASS.
- MD-03 일회용 PostgreSQL SAVEPOINT/DB CHECK/전체 rollback 검증 별도로 PASS.
- **이번 병합 충돌 검사는 아직 MiniPC에서 실행되지 않았다.** 별도 테스트 결과를 받기 전 충돌 건수를 단정하지 않는다.
- 실제 GitHub-hosted Actions 검증, PR draft 해제/병합, 운영 DB migration/배포 및 KIS 실호출은 여전히 별도 승인 항목.


## 실제 MiniPC 쌍별 병합 출력 (2026-11-23)
- Bash 아카이브 SHA `beacf5d3`, unittest **6/6 PASS**, GitHub pinned refs 및 23개 핵심 Git blob 일치 PASS.
- 7개 pairwise 결과: main+ci 0, ci+pr24 2, ci+pr25 2, ci+pr26 3, pr24+pr25 2, pr24+pr26 2, pr25+pr26 2. **총 13개는 중복 포함**.
- 충돌 고유 파일 정확히 3개: `AGENTS.md`, `docs/ROADMAP.md`, `.github/workflows/ci.yml`. 나머지 KIS·가격·migration 핵심 파일은 이번 pairwise 결과에서 충돌 없음.
- 실제 순차 검증은 별도 신규 `scripts/ci/sequential_merge_rehearsal.py`와 `docs/CI_KIS_SEQUENTIAL_REHEARSAL.md` 참고. 현재 미실행.
