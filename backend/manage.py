"""Operational commands.

    python manage.py migrate                      apply pending schema migrations
    python manage.py create-user USERNAME ROLE    create a user (password is prompted, never a CLI argument)
    python manage.py list-users
    python manage.py verify-audit                 check the audit hash chain
    python manage.py purge-audio                  delete retained recordings past their retention window
"""
import argparse
import getpass
import os
import sys

from audit import verify_chain
from auth import create_user
from asr import jobs as asr_jobs
from database import SessionLocal, init_db
from models_care import USER_ROLES, User


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="CareRouter AI management commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    cu = sub.add_parser("create-user")
    cu.add_argument("username")
    cu.add_argument("role", choices=USER_ROLES)
    cu.add_argument("--full-name", default=None)
    cu.add_argument("--department", default=None, help="team whose queue a coordinator/pharmacist may see")
    cu.add_argument("--patient-id", type=int, default=None, help="required for role 'patient'")
    cu.add_argument("--password-env", default=None, metavar="VAR",
                    help="read the password from this environment variable instead of prompting")
    sub.add_parser("list-users")
    sub.add_parser("verify-audit")
    sub.add_parser("purge-audio")
    args = parser.parse_args(argv)

    init_db()   # creates missing tables and applies migrations
    if args.command == "migrate":
        print("Schema is up to date.")
        return 0

    with SessionLocal() as db:
        if args.command == "create-user":
            if args.password_env:
                password = os.environ.get(args.password_env, "")
                if not password:
                    print(f"Environment variable {args.password_env} is not set or empty.", file=sys.stderr)
                    return 1
            else:
                password = getpass.getpass("Password (min 12 chars, mixed case, with a digit): ")
                if password != getpass.getpass("Repeat password: "):
                    print("Passwords do not match.", file=sys.stderr)
                    return 1
            try:
                user = create_user(db, username=args.username, password=password,
                                   full_name=args.full_name or args.username, role=args.role,
                                   department=args.department, patient_id=args.patient_id)
                db.commit()
            except ValueError as exc:
                db.rollback()
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            print(f"Created {user.role} '{user.username}' (id {user.id}).")
        elif args.command == "list-users":
            for u in db.query(User).order_by(User.id):
                state = "active" if u.is_active else "disabled"
                print(f"{u.id:>4}  {u.username:<24} {u.role:<12} {u.department or '-':<30} {state}")
        elif args.command == "verify-audit":
            ok, broken = verify_chain(db)
            print("Audit chain intact." if ok else f"Audit chain BROKEN at event {broken}.")
            return 0 if ok else 2
        elif args.command == "purge-audio":
            print(f"Removed {asr_jobs.purge_expired_audio(db)} expired recording(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
