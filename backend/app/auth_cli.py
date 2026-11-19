"""Use an interactive console on the personal MiniPC to initialize owner once."""
import getpass
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.auth import bootstrap_owner


def main() -> int:
    if sys.argv[1:] != ["init-owner"]:
        print("Usage: python -m app.auth_cli init-owner", file=sys.stderr)
        return 2
    try:
        username = input("소유자 로그인 아이디: ").strip()
        password = getpass.getpass("새 비밀번호 (12자 이상): ")
        repeat = getpass.getpass("비밀번호 확인: ")
        if password != repeat:
            print("비밀번호가 일치하지 않습니다.", file=sys.stderr)
            return 1
        bootstrap_owner(username, password)
    except (ValueError, SQLAlchemyError) as exc:
        print(f"계정 초기화 실패: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        # Best effort: Python strings are immutable and cannot be memory-wiped.
        password = None
        repeat = None
    print("소유자 계정 초기화 성공. 비밀번호는 출력하지 않습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
