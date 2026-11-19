# OPS-01 — 독립 DB 복원 검증 및 정기 백업 (준비 단계)

## 현재 상태

- 운영 FolioSentry는 기존 `foliosentry-prod`의 PostgreSQL·Backend·Frontend로 정상 서비스 중. **이번 PR은 MiniPC Docker/DB를 변경하지 않는다.**
- 2026-11-19 최초 HTTPS 배포 때 `pg_dump` Custom Format + SHA256 + archive stream read PASS 확인. **2026-11-19 MiniPC 실제 백업을 격리 PostgreSQL에 복원하고 인증 스키마·소유자 1명 조회 PASS**.
- 신규 `scripts/verify-backup-restore.sh`는 **검증된 단일 백업**을 별도 PostgreSQL 17 컨테이너의 임시 tmpfs에 복원해 auth schema/owner를 검사. `--network none`, host port 없음, 운영 DB 연결 없음, 실행 종료 시 임시 컨테이너만 정리.
- `scripts/run-daily-backup.sh`는 운영 DB를 **읽기 전용 pg_dump**해 일일 Custom Format 백업 생성, SHA256 및 아카이브 검증 후 **14일보다 오래된 일일 백업 중 검증 가능한 쌍만** 정리. `prepublish-` 백업과 미확인 파일은 자동 삭제 금지.
- GitHub CI의 격리 synthetic 데이터베이스에서 생성→복원→일일 보관 정책을 자동 시험한다. CI PASS가 실제 MiniPC 복원 PASS를 대체하지 않는다.

## 1. 실제 MiniPC 복원 시험 (별도 승인된 실행 단계)

먼저 저장소 `main` HEAD와 CI를 확인한 뒤, MiniPC에서 복원 전용 명령만 실행한다.

```bash
cd ~/folio-sentry
# OPS-01 PR이 검토·병합되고 로컬 main 동기화된 상태에서
bash -n scripts/verify-backup-restore.sh

ARCHIVE="$HOME/.local/share/folio-sentry/backups/<실제-prepublish-백업명>.pgdump"
bash scripts/verify-backup-restore.sh --confirm-isolated-restore "$ARCHIVE"
```

**공개된 DB/Backend/Frontend를 중지·변경하지 않음.** 검증 작업은 새 임시 PostgreSQL 컨테이너 하나를 생성하므로 엄밀한 의미의 읽기 전용 Docker 작업은 아니다. 사용자 승인 없이 실행하지 않는다.

기대 결과:

```text
FOLIOSENTRY_RESTORE_SOURCE=CHECKSUM_VERIFIED
FOLIOSENTRY_RESTORE_MODE=ISOLATED_EPHEMERAL_NO_NETWORK
FOLIOSENTRY_RESTORE_SCHEMA_AND_OWNER_PASS
PRODUCTION_DB_READ_ONLY=YES
PRODUCTION_CONTAINERS_MODIFIED=NO
FOLIOSENTRY_ISOLATED_RESTORE_TEST_PASS
```

복원 성공은 이번 인증 스키마/소유자 데이터 복원이 가능함을 확인한 것으로, 전체 장비 복구·다른 PostgreSQL 버전·계정 로그인/비밀번호 복구 시험까지 증명하지 않는다. 복원용 임시 DB에는 실제 비밀번호 *해시*가 들어가므로 네트워크 격리·출력 최소화·종료 시 자동 삭제가 필수다.

### MiniPC 실제 복원 인수 결과 (2026-11-19)

실행 대상: 최초 운영 배포에서 생성한 `prepublish-20261119T052831Z.Mo0rXRKV.pgdump`. 실제 백업 파일·SHA256·비밀번호 해시·DB 레코드는 공개하지 않음.

```text
FOLIOSENTRY_RESTORE_SOURCE=CHECKSUM_VERIFIED
FOLIOSENTRY_RESTORE_MODE=ISOLATED_EPHEMERAL_NO_NETWORK
FOLIOSENTRY_RESTORE_SCHEMA_AND_OWNER_PASS
PRODUCTION_DB_READ_ONLY=YES
PRODUCTION_CONTAINERS_MODIFIED=NO
EPHEMERAL_POSTGRES_CLEANUP=ON_EXIT
FOLIOSENTRY_ISOLATED_RESTORE_TEST_PASS
FOLIOSENTRY_OPS01_RESTORE_PROBE_PASS
```

이는 **복원과 인증 스키마/소유자 건수 조회 성공**을 입증한다. 스크립트는 `EXIT` 시 임시 컨테이너를 중지하도록 되어 있지만, 출력된 `CLEANUP=ON_EXIT` 메시지는 실제 삭제를 별도 확인했다는 뜻은 아니다. 외부 장비 복구·복원 후 로그인·장기 보존/암호화는 여전히 미검증이다.

### 다음 운영 단계 (아직 실행하지 않음)

**2026-11-19 MiniPC 수동 일일 백업 1회 PASS.** `scripts/backup-db.sh --confirm-daily-backup`로 신규 백업 한 건만 생성했고 이전 파일 삭제/운영 데이터 변경 없음. 시스템 타이머 등록 여부는 별도 승인 전 사전검사로 결정한다.

## 2. 정기 백업 동작 (아직 운영 자동 등록 안 함)

- 기본 주기 제안: **매일 03:30 MiniPC 로컬 시간**. `ops/systemd/foliosentry-backup.timer`은 파일만 추가했으며 **설치·enable·start는 아직 하지 않음**.
- 경로: `~/.local/share/folio-sentry/backups/daily-YYYYMMDDTHHMMSSZ.<임의8자>.pgdump`
- 매일 새 아카이브·SHA256 성공 → 검증된 이전 daily 쌍만 14일 보관 정책에 따라 제거
- `prepublish-`, `manual-`, 파일명 규칙이 다른 파일, 손상된 검증파일은 삭제하지 않음
- 스크립트 시작에 `flock`을 획득하여 겹치는 일일 백업 실행 거부. 사용자 계정 및 사용자 전용 `0700` 폴더/파일 `0600` 사용
- 별도 원격 저장소·암호화·백업 복원 정기 점검·알림은 아직 미구현. 서버 디스크 장애 시 로컬 백업도 손실될 수 있다

별도 승인 후 수동 1회 동작 확인(이 명령은 **실제 운영 DB로부터 새 백업을 생성**하며 오래된 일일 백업을 삭제할 수 있음):

```bash
bash scripts/run-daily-backup.sh --confirm-daily-backup
```

## 3. systemd 사용자 타이머 등록 (추후 명시적 승인 후)

```bash
# 아래는 운영 자동화 설정을 변경하므로 사용자 승인 이전에는 실행 금지.
install -d -m 700 "$HOME/.config/systemd/user"
install -m 644 ops/systemd/foliosentry-backup.service "$HOME/.config/systemd/user/"
install -m 644 ops/systemd/foliosentry-backup.timer "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now foliosentry-backup.timer

# 확인 (비밀정보 출력 금지)
systemctl --user is-enabled foliosentry-backup.timer
systemctl --user list-timers foliosentry-backup.timer
loginctl show-user "$USER" -p Linger
```

`Linger=no`이면 사용자가 로그아웃한 상태에서 user systemd timer가 실행되지 않을 수 있다. 이 작업에서는 `loginctl enable-linger`를 자동 호출하지 않는다. 사용자 재승인 및 다른 사용자 서비스 영향 검토 후 결정한다.

## 4. 절대 금지 및 후속

- `docker compose down -v`, `docker volume rm`, 운영 DB `pg_restore`, 기존 Traefik·PickNext·공유기 재설정 금지
- 백업 파일, SHA256 원문, 로그인 해시, 원본 데이터, DB secret, `acme.json`을 GitHub·채팅에 올리지 않는다
- 정상 운영 중 `deploy.sh publish` 재실행 금지. OPS-01 검증은 독립적으로 진행
- 외부 저장소의 암호화 백업·복원 절차, 실패 알림 및 ACME 저장소 백업은 별도 계획

## OPS-01 수동 일일 백업 인수 결과 (2026-11-19)

- `main@d65ff72b98b775096a560293386c49813ed7074c` 동기화, 임시 복원 컨테이너 잔존 여부 조회 PASS.
- 새 백업 `daily-20261119T062547Z.JrHzGbdU.pgdump` 생성. `FOLIOSENTRY_DAILY_BACKUP_VERIFY_PASS`, `BACKUP_SHA256_CHECK=PASS`, `ARCHIVE_READABILITY=PASS_NOT_RESTORE_TRIAL`, `FOLIOSENTRY_DAILY_BACKUP_MANUAL_PASS`.
- 데이터 변경 없음. 이번 **daily 아카이브 자체의 독립 복원 시험은 미실행**이며, 앞선 `prepublish` 아카이브의 격리 복원은 PASS.
- 여전히 운영 타이머 미설치·미활성화. 다음은 systemd 사용자 서비스 연결 상태, `Linger`, 서버 시간대, 중복 유닛 존재 여부 **읽기 전용**으로 점검한다.
- systemd 활성화 시 `Persistent=true`이므로 과거 03:30 실행 시각이 지나 있었다면 서비스가 즉시 한번 실행될 수 있다. 타이머 설치·enable·start는 사용자 별도 승인 후.

## OPS-01 자동 백업 타이머 활성화 인수 결과 — 2026-11-19

- MiniPC 점검: `Timezone=Asia/Seoul`, `systemctl --user` active, `Linger=yes`, 동일 이름의 기존 사용자 유닛 없음.
- `ops/systemd/foliosentry-backup.service`와 `.timer`를 사용자 유닛으로 설치. `systemctl --user enable --now foliosentry-backup.timer` 성공, `FOLIOSENTRY_DAILY_TIMER_ACTIVATION_PASS` 출력 확인.
- 최초 예정 시간: **2026-11-20 03:30 KST** (`systemctl --user list-timers` 표시). 사용자가 pager에서 `q`를 눌러 종료한 뒤 최종 마커를 확인함.
- 타이머는 03:30 `scripts/run-daily-backup.sh --confirm-daily-backup`를 호출하도록 구성. 새 백업 성공 후 검증된 14일 초과 `daily-` 백업 쌍만 정리, `prepublish-` 백업 보존.
- **자동 예약이 정상 활성화됐다는 뜻이지 첫 자동 백업 실행 성공을 의미하지 않음.** 2026-11-20 03:30 이후 `systemctl --user show ...` 및 `journalctl --user -u foliosentry-backup.service`로 실제 실행 결과와 새 daily 아카이브를 확인해야 함.
- 이메일/모바일 실패 알림, 오프사이트/암호화 백업, ACME 저장소 백업은 미구현. 기존 FolioSentry API/DB/Traefik/PickNext는 변경하지 않음.
