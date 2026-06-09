"""Create an admin user interactively.

Usage:
    python scripts/create_admin.py <email>

The password is prompted securely (not echoed, not stored in shell history).
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# Make the project root importable regardless of where the script is called from
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.features.auth.models import UserRole
from app.features.auth.repository import create_user, get_user_by_email


async def main(email: str, password: str) -> None:
    async with AsyncSessionLocal() as session:
        existing = await get_user_by_email(session, email)
        if existing:
            print(f"User '{email}' already exists (role: {existing.role.value})")
            sys.exit(1)
        user = await create_user(
            session,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.admin,
        )
        print(f"Admin created: {user.email}  (id={user.id})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("email", help="Admin email address")
    args = parser.parse_args()

    password = getpass.getpass("Password (min 8 chars): ")
    confirm = getpass.getpass("Confirm password: ")

    if len(password) < 8:
        print("Password must be at least 8 characters")
        sys.exit(1)
    if password != confirm:
        print("Passwords do not match")
        sys.exit(1)

    asyncio.run(main(args.email, password))
