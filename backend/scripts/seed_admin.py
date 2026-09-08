#!/usr/bin/env python3
"""
seed_admin.py — Bootstrap the first admin user for ProjectXY.

Usage (run from the backend/ directory):
    python scripts/seed_admin.py

Or with custom values:
    ADMIN_EMAIL=ciso@corp.com ADMIN_PASSWORD=S3cr3t! python scripts/seed_admin.py

The script is idempotent: running it twice will not create a duplicate.
It creates a default Tenant ('HQ') if none exists, then creates the admin user
under that tenant.
"""
import os
import sys
import getpass
import uuid

# ── Path bootstrap ──────────────────────────────────────────────────────────
# Allow running from both project root and backend/ directory
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from sqlalchemy.orm import Session
from app.infrastructure.session import SessionLocal
from app.models.models import Base, Tenant, User
from app.core.security import get_password_hash

# ── Configuration (env-overridable) ─────────────────────────────────────────
DEFAULT_TENANT_NAME   = os.getenv("ADMIN_TENANT_NAME",   "HQ")
DEFAULT_TENANT_DOMAIN = os.getenv("ADMIN_TENANT_DOMAIN", "hq.local")
DEFAULT_EMAIL         = os.getenv("ADMIN_EMAIL",         "admin@projectxy.local")
DEFAULT_FULL_NAME     = os.getenv("ADMIN_FULL_NAME",     "System Administrator")


def _get_or_create_tenant(db: Session) -> Tenant:
    """Returns the HQ tenant, creating it if it doesn't exist."""
    tenant = db.query(Tenant).filter(Tenant.name == DEFAULT_TENANT_NAME).first()
    if not tenant:
        tenant = Tenant(
            id=uuid.uuid4(),
            name=DEFAULT_TENANT_NAME,
            domain=DEFAULT_TENANT_DOMAIN,
            subscription_tier="enterprise",
            is_active=True,
        )
        db.add(tenant)
        db.flush()  # Get the ID without committing yet
        print(f"  [+] Created tenant  : {DEFAULT_TENANT_NAME} ({tenant.id})")
    else:
        print(f"  [~] Tenant exists   : {DEFAULT_TENANT_NAME} ({tenant.id})")
    return tenant


def _get_password(env_key: str = "ADMIN_PASSWORD") -> str:
    """Read password from env or prompt interactively (never echoed)."""
    password = os.getenv(env_key)
    if password:
        return password

    print("\nNo ADMIN_PASSWORD env var set. Enter password interactively:")
    while True:
        password = getpass.getpass("  Password         : ")
        if len(password) < 12:
            print("  ✗  Password must be at least 12 characters. Try again.")
            continue
        confirm = getpass.getpass("  Confirm password : ")
        if password != confirm:
            print("  ✗  Passwords do not match. Try again.")
            continue
        break
    return password


def seed_admin() -> None:
    print("=" * 55)
    print("  ProjectXY — Admin Seed Script")
    print("=" * 55)

    email    = DEFAULT_EMAIL
    fullname = DEFAULT_FULL_NAME

    # Prompt for values not provided via env
    if not os.getenv("ADMIN_EMAIL"):
        entered = input(f"  Admin email [{email}] : ").strip()
        if entered:
            email = entered

    if not os.getenv("ADMIN_FULL_NAME"):
        entered = input(f"  Full name   [{fullname}] : ").strip()
        if entered:
            fullname = entered

    password = _get_password()

    db: Session = SessionLocal()
    try:
        # 1 — Ensure tenant exists
        tenant = _get_or_create_tenant(db)

        # 2 — Check for existing admin with this email
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"\n  [!] User already exists: {email}")
            update = input("      Update password? [y/N] : ").strip().lower()
            if update == "y":
                existing.hashed_password = get_password_hash(password)
                existing.role = "admin"
                existing.is_active = True
                db.commit()
                print(f"  [✓] Password updated for {email}.")
            else:
                print("  [~] No changes made.")
            return

        # 3 — Create the admin user
        admin = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            full_name=fullname,
            hashed_password=get_password_hash(password),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()

        print(f"\n  [✓] Admin user created successfully!")
        print(f"      Email     : {email}")
        print(f"      Full name : {fullname}")
        print(f"      Role      : admin")
        print(f"      Tenant    : {DEFAULT_TENANT_NAME}")
        print(f"      ID        : {admin.id}")
        print()

    except Exception as exc:
        db.rollback()
        print(f"\n  [✗] Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
