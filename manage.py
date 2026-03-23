#!/usr/bin/env python3
"""Management CLI commands - create-admin, remove-admin, reset-password."""
import argparse
import sys

import bcrypt


def get_app():
    from server.app import create_app
    return create_app()


def create_admin(args):
    app = get_app()
    with app.app_context():
        from server.extensions import db
        from server.models.user import User

        if User.query.filter_by(username=args.username).first():
            print(f"Error: username '{args.username}' already exists")
            sys.exit(1)

        password_hash = bcrypt.hashpw(
            args.password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        user = User(
            username=args.username,
            password_hash=password_hash,
            role='admin',
            created_by='system',
        )
        db.session.add(user)
        db.session.commit()
        print(f"Admin '{args.username}' created successfully")


def remove_admin(args):
    app = get_app()
    with app.app_context():
        from server.extensions import db
        from server.models.user import User

        user = User.query.filter_by(username=args.username).first()
        if not user:
            print(f"Error: user '{args.username}' not found")
            sys.exit(1)

        # Rule 9: ensure at least 1 admin remains
        admin_count = User.query.filter_by(role='admin').count()
        if user.role == 'admin' and admin_count <= 1:
            print("Error: cannot remove the last admin. System must have at least 1 admin.")
            sys.exit(1)

        db.session.delete(user)
        db.session.commit()
        print(f"User '{args.username}' removed successfully")


def reset_password(args):
    app = get_app()
    with app.app_context():
        from server.extensions import db
        from server.models.user import User

        user = User.query.filter_by(username=args.username).first()
        if not user:
            print(f"Error: user '{args.username}' not found")
            sys.exit(1)

        if not args.password:
            print("Error: --password is required")
            sys.exit(1)

        user.password_hash = bcrypt.hashpw(
            args.password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
        user.failed_login_count = 0
        user.locked_until = None
        db.session.commit()
        print(f"Password for '{args.username}' reset successfully")


def main():
    parser = argparse.ArgumentParser(description='NetworkStatus-Rabbit Management CLI')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # create-admin
    p_create = subparsers.add_parser('create-admin', help='Create a new admin user')
    p_create.add_argument('--username', required=True, help='Admin username')
    p_create.add_argument('--password', required=True, help='Admin password')

    # remove-admin
    p_remove = subparsers.add_parser('remove-admin', help='Remove a user')
    p_remove.add_argument('--username', required=True, help='Username to remove')

    # reset-password
    p_reset = subparsers.add_parser('reset-password', help='Reset a user password')
    p_reset.add_argument('--username', required=True, help='Username')
    p_reset.add_argument('--password', required=True, help='New password')

    args = parser.parse_args()

    if args.command == 'create-admin':
        create_admin(args)
    elif args.command == 'remove-admin':
        remove_admin(args)
    elif args.command == 'reset-password':
        reset_password(args)


if __name__ == '__main__':
    main()
