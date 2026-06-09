"""Reset password for an existing user.

Usage:
    python scripts/reset_password.py <email>
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.features.auth.repository import get_user_by_email, update_user


async def main(email: str, password: str) -> None:
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, email)
        if not user:
            print(f"No user found with email '{email}'")
            sys.exit(1)
        await update_user(session, user, hashed_password=hash_password(password))
        print(f"Password updated for: {user.email} (role: {user.role.value})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset a user's password")
    parser.add_argument("email", help="User email address")
    args = parser.parse_args()

    password = getpass.getpass("New password (min 8 chars): ")
    confirm = getpass.getpass("Confirm password: ")

    if len(password) < 8:
        print("Password must be at least 8 characters")
        sys.exit(1)
    if password != confirm:
        print("Passwords do not match")
        sys.exit(1)

    asyncio.run(main(args.email, password))
