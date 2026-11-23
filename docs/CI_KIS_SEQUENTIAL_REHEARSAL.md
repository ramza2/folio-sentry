# OPS-CI06 — 실제 순서대로 합성 Git 병합 검증 (2026-11-23)

## 배경 및 선행 실사
MiniPC의 `review/ci-kis-merge-rehearsal-20261123@beacf5d3c02678c8b4bb3a58d808829d4266707c` 검사 결과:
- 순수 unittest 6/6 PASS, Git SHA 확인 PASS, 핵심 23개 Git blob 통합본과 일치.
- 7개 **독립 쌍별(pairwise)** Git 병합 총 충돌 **13건**. 중복을 제외한 충돌 대상은 `AGENTS.md`, `docs/ROADMAP.md`, `.github/workflows/ci.yml` **3개 파일**.
- `main+ci=0`, `ci+#24=2`, `ci+#25=2`, `ci+#26=3`, `#24+#25=2`, `#24+#26=2`, `#25+#26=2`.
- 위 수치는 순차적으로 병합할 때 생기는 실제 누적 충돌 수가 아니다.

## 이번 단계
`scripts/ci/sequential_merge_rehearsal.py`와 `scripts/ci/test_sequential_merge_rehearsal.py` 신규 작성.

1. MiniPC FolioSentry Git root에서 GitHub Private origin 주소만 확인(토큰 포함 주소 거부).
2. 네트워크 fetch는 `--run`에서만, **사용자 저장소와 분리된 임시 bare Git 저장소**에만 수행. main/CI/PR #24/#25/#26/통합본의 이전에 확인한 **6개 SHA 고정**.
3. 임시 저장소에서 `CI → #24 → #25 → #26`을 `git merge-tree --write-tree --name-only`로 **실제 순서대로** 평가하고 단계별 synthetic merge commit을 임시 bare Git에만 작성(`git commit-tree`). GitHub push/PR merge/사용자 worktree checkout 없음.
4. 각 단계의 허용 충돌 파일: CI 단계는 **0개**, #24와 #25는 `AGENTS.md`, `docs/ROADMAP.md`, #26은 이 두 문서와 `.github/workflows/ci.yml`. 그 외 코드 충돌 시 즉시 중단(fail closed).
5. 충돌 발생 시 임시 Git index에서만 검토 완료 통합 브랜치 `review/ci-kis-offline-integration-20261123@0c1c22a`의 세 파일에 해당하는 Git blob으로 치환(실 데이터/현재 운영 파일 편집 없음).
6. 완료 후 합성 최종 결과의 **23개 CI/KIS 핵심 blob**과 충돌 해소 대상 **3개 파일**이 해당 검토본과 동일한지 확인. 통합 검토본에서만 새로 만든 별도 테스트·검증 스크립트는 후속 포팅 대상으로 식별하고 목록 출력.

## 중요한 해석 경계
- 이 검사는 **임시 bare Git 안에서의 순차적인 3-way 합성 병합**이다. 정상적인 Git merge commit을 GitHub에 생성하지 않으므로 실제 PR 병합/승인이 아니다.
- 각 중간 단계에 사용한 `AGENTS.md`·`docs/ROADMAP.md` 충돌 해소 blob은 **최종 통합 검토본 기준**이다. 따라서 #24/#25 단계 중간 결과는 추후 PR 내용을 미리 언급할 수 있다. **중간 단계 커밋을 운영/실제 main 병합용으로 사용 금지**.
- 전체 통합 검토 브랜치에는 PR #27 및 별도 후속 검증에서만 제공되는 파일이 있다. 이는 CI/#24/#25/#26 독립 브랜치 병합으로 자동 포함되지 않는다. `SEQUENTIAL_FOLLOWUP_NOT_INCLUDED` 목록이 나오더라도 코드 충돌은 아니다.
- 실제 GitHub Actions job·required check/운영 가격 시세 최종성·운영 DB 스키마 변경 검증은 별도. Private 저장소 및 실제 KIS 계좌/비밀파일/토큰/운영 DB 불변.

## MiniPC 안전 검증 절차
1. 최신 검토 브랜치 SHA를 GitHub에서 확인하고 Git archive로 두 Python 스크립트 + 기존 `scripts/ci/merge_rehearsal.py`만 임시 추출한다.
2. Python stdlib `unittest`로 테스트 12개(기존 6 + 신규 6) 실행. 단위 테스트의 Git fixture는 로컬 임시 저장소에서만 실행, **네트워크 사용 없음**.
3. 원본 `~/folio-sentry` 경로에서 `python3 -B <archive>/scripts/ci/sequential_merge_rehearsal.py --preflight` 실행. Git remote/버전만 읽음.
4. 같은 위치에서 `--run` 실행. GitHub의 승인된 6개 private branch를 임시 bare 저장소에 fetch한 뒤 synthetic merge 수행. 표준 출력에는 충돌 파일 이름·단계·검증 마커만 표시.
5. `FOLIOSENTRY_SEQUENTIAL_REVIEW_COMPLETE_NOT_PRODUCTION_APPROVAL`이 나오면 합성 분석 종료. 오류 시 출력한 FAIL 코드와 경로를 그대로 보고. `--run` 중단되더라도 OS TemporaryDirectory에서 합성 Git 저장소를 정리한다.

## 진행 상태
- [x] MiniPC 쌍별 병합 7개·13건 중복 충돌, 3개 고유 파일 실사 완료.
- [x] 임시 bare Git 순차 합성 병합 및 코드 blob 보존 게이트 구현.
- [x] 오프라인 Git fixture 계약 검증 소스 작성.
- [ ] MiniPC 12개 unittest 및 실제 읽기 전용 sequential rehearsal PASS 확인.
- [ ] 실패/미해소 충돌이 발견되면 리뷰 브랜치에만 수정. 사용자 별도 승인 없이 main/PR/Actions/운영 변경 금지.
