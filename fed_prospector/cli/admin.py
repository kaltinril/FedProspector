"""System administration CLI commands.

Commands: create-sysadmin, create-org, list-orgs, invite-user, list-org-members, disable-user, enable-user, reset-password
"""

import hashlib
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone

import click

from config.logging_config import setup_logging


@click.command("create-sysadmin")
@click.option("--username", required=True, help="Login username")
@click.option("--email", required=True, help="Email address")
@click.option("--display-name", required=True, help="Full display name")
@click.option("--org-name", default="System Administration",
              help="Organization name (default: System Administration)")
def create_sysadmin(username, email, display_name, org_name):
    """Bootstrap a system admin user with full privileges.

    Creates an organization (if needed) and an admin user who can then
    use the API to create client organizations and invite users.

    Examples:
        python main.py admin create-sysadmin --username admin --email admin@myco.com \\
            --display-name "Admin User"

        python main.py admin create-sysadmin --username admin --email admin@myco.com \\
            --display-name "Admin" --org-name "Acme Corp"
    """
    logger = setup_logging()

    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)

    from db.connection import get_connection
    from utils.password import hash_password

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Check username uniqueness
        cursor.execute(
            "SELECT user_id FROM app_user WHERE LOWER(username) = LOWER(%s)",
            (username,),
        )
        if cursor.fetchone():
            click.echo(f"ERROR: Username '{username}' already exists.")
            sys.exit(1)

        # Check email uniqueness
        cursor.execute(
            "SELECT user_id FROM app_user WHERE LOWER(email) = LOWER(%s)",
            (email,),
        )
        if cursor.fetchone():
            click.echo(f"ERROR: Email '{email}' already exists.")
            sys.exit(1)

        # Find or create organization
        cursor.execute(
            "SELECT organization_id FROM organization WHERE LOWER(name) = LOWER(%s)",
            (org_name,),
        )
        row = cursor.fetchone()
        if row:
            org_id = row["organization_id"]
            logger.info("Using existing organization '%s' (org_id=%d)", org_name, org_id)
        else:
            slug = _generate_slug(org_name)
            cursor.execute(
                "INSERT INTO organization (name, slug, is_active, max_users, subscription_tier) "
                "VALUES (%s, %s, 'Y', 50, 'enterprise')",
                (org_name, slug),
            )
            org_id = cursor.lastrowid
            logger.info("Created organization '%s' (org_id=%d)", org_name, org_id)

        # Hash password (BCrypt Enhanced — compatible with C# API)
        password_hash = hash_password(password)

        # Create admin user
        cursor.execute(
            "INSERT INTO app_user "
            "(organization_id, username, display_name, email, password_hash, "
            " role, is_active, is_admin, mfa_enabled, org_role, "
            " force_password_change, failed_login_attempts) "
            "VALUES (%s, %s, %s, %s, %s, 'USER', 'Y', 'Y', 'N', 'owner', 'N', 0)",
            (org_id, username, display_name, email, password_hash),
        )
        user_id = cursor.lastrowid
        conn.commit()

        click.echo(
            f"Created system admin '{username}' "
            f"(user_id={user_id}, org_id={org_id}, org='{org_name}')"
        )
        click.echo(f"You can now login at POST /api/v1/auth/login with this email and password.")

    except Exception as e:
        conn.rollback()
        logger.exception("Failed to create system admin")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


def _generate_slug(name: str) -> str:
    """Generate a URL-safe slug from an organization name.

    Lowercase, replace spaces with hyphens, strip non-alphanumeric except hyphens.
    """
    slug = name.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


@click.command("create-org")
@click.option("--name", required=True, help="Organization name")
@click.option("--slug", default=None, help="URL slug (auto-generated from name if omitted)")
@click.option("--max-users", default=10, type=int, help="Maximum users (default: 10)")
@click.option("--tier", default="trial", help="Subscription tier (default: trial)")
def create_org(name, slug, max_users, tier):
    """Create a new organization.

    Examples:
        python main.py admin create-org --name "Acme Corp" --slug acme-corp

        python main.py admin create-org --name "Acme Corp" --max-users 25 --tier professional
    """
    logger = setup_logging()

    if slug is None:
        slug = _generate_slug(name)

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Check slug uniqueness
        cursor.execute(
            "SELECT organization_id FROM organization WHERE slug = %s",
            (slug,),
        )
        if cursor.fetchone():
            click.echo(f"ERROR: Slug '{slug}' already exists.")
            sys.exit(1)

        cursor.execute(
            "INSERT INTO organization (name, slug, is_active, max_users, subscription_tier) "
            "VALUES (%s, %s, 'Y', %s, %s)",
            (name, slug, max_users, tier),
        )
        org_id = cursor.lastrowid
        conn.commit()

        click.echo(f"Created organization '{name}' (org_id={org_id}, slug={slug})")

    except Exception as e:
        conn.rollback()
        logger.exception("Failed to create organization")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@click.command("list-orgs")
def list_orgs():
    """List all organizations.

    Examples:
        python main.py admin list-orgs
    """
    logger = setup_logging()

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT o.organization_id, o.name, o.slug, o.is_active, "
            "       o.max_users, o.subscription_tier, "
            "       (SELECT COUNT(*) FROM app_user u "
            "        WHERE u.organization_id = o.organization_id) AS user_count "
            "FROM organization o ORDER BY o.organization_id"
        )
        rows = cursor.fetchall()

        if not rows:
            click.echo("No organizations found.")
            return

        # Print header
        click.echo(f"{'ID':>4}  {'Name':<30}  {'Slug':<25}  {'Active':<6}  "
                    f"{'Users':<7}  {'Tier':<15}")
        click.echo("-" * 95)

        for row in rows:
            click.echo(
                f"{row['organization_id']:>4}  "
                f"{row['name']:<30}  "
                f"{row['slug']:<25}  "
                f"{row['is_active']:<6}  "
                f"{row['user_count']:<7}  "
                f"{row['subscription_tier'] or '':<15}"
            )

        click.echo(f"\n{len(rows)} organization(s) found.")

    except Exception as e:
        logger.exception("Failed to list organizations")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@click.command("invite-user")
@click.option("--email", required=True, help="Email address to invite")
@click.option("--org-id", required=True, type=int, help="Organization ID")
@click.option("--role", default="member", type=click.Choice(["member", "admin", "owner"]),
              help="Organization role (default: member)")
def invite_user(email, org_id, role):
    """Create an invitation for a user to join an organization.

    Examples:
        python main.py admin invite-user --email user@acme.com --org-id 2

        python main.py admin invite-user --email user@acme.com --org-id 2 --role admin
    """
    logger = setup_logging()

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Verify org exists
        cursor.execute(
            "SELECT organization_id, name FROM organization WHERE organization_id = %s",
            (org_id,),
        )
        org = cursor.fetchone()
        if not org:
            click.echo(f"ERROR: Organization with org_id={org_id} not found.")
            sys.exit(1)

        # Generate invite code
        now = datetime.now(timezone.utc)
        raw = f"{email}:{org_id}:{now.isoformat()}:{secrets.token_hex(16)}"
        invite_code = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        expires_at = now + timedelta(days=7)

        # Look up the sysadmin user_id to use as the inviter
        cursor.execute(
            "SELECT user_id FROM app_user WHERE is_admin = 'Y' ORDER BY user_id LIMIT 1"
        )
        admin_row = cursor.fetchone()
        if not admin_row:
            click.echo("ERROR: No admin user found. Create a sysadmin first with 'python main.py admin create-sysadmin'.")
            sys.exit(1)
        invited_by = admin_row["user_id"]

        cursor.execute(
            "INSERT INTO organization_invite "
            "(organization_id, email, invite_code, org_role, invited_by, expires_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (org_id, email, invite_code, role, invited_by, expires_at),
        )
        conn.commit()

        click.echo(f"Invite created for {email} (code: {invite_code})")
        click.echo(f"Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo("Share this code with the user to complete registration.")

    except Exception as e:
        conn.rollback()
        logger.exception("Failed to create invite")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@click.command("list-org-members")
@click.option("--org-id", required=True, type=int, help="Organization ID")
def list_org_members(org_id):
    """List members of an organization.

    Examples:
        python main.py admin list-org-members --org-id 2
    """
    logger = setup_logging()

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Verify org exists
        cursor.execute(
            "SELECT organization_id, name FROM organization WHERE organization_id = %s",
            (org_id,),
        )
        org = cursor.fetchone()
        if not org:
            click.echo(f"ERROR: Organization with org_id={org_id} not found.")
            sys.exit(1)

        click.echo(f"Members of '{org['name']}' (org_id={org_id}):\n")

        cursor.execute(
            "SELECT user_id, username, display_name, email, org_role, "
            "       is_active, is_admin, last_login_at "
            "FROM app_user WHERE organization_id = %s "
            "ORDER BY user_id",
            (org_id,),
        )
        rows = cursor.fetchall()

        if not rows:
            click.echo("No members found.")
            return

        # Print header
        click.echo(f"{'ID':>4}  {'Username':<20}  {'Display Name':<25}  {'Email':<30}  "
                    f"{'Role':<8}  {'Active':<6}  {'Admin':<5}  {'Last Login':<19}")
        click.echo("-" * 125)

        for row in rows:
            last_login = (row["last_login_at"].strftime("%Y-%m-%d %H:%M:%S")
                          if row["last_login_at"] else "never")
            click.echo(
                f"{row['user_id']:>4}  "
                f"{row['username']:<20}  "
                f"{row['display_name']:<25}  "
                f"{(row['email'] or ''):<30}  "
                f"{row['org_role']:<8}  "
                f"{row['is_active']:<6}  "
                f"{row['is_admin']:<5}  "
                f"{last_login:<19}"
            )

        click.echo(f"\n{len(rows)} member(s) found.")

    except Exception as e:
        logger.exception("Failed to list org members")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@click.command("disable-user")
@click.option("--user-id", required=True, type=int, help="User ID to disable")
def disable_user(user_id):
    """Disable a user account and revoke all active sessions.

    Examples:
        python main.py admin disable-user --user-id 5
    """
    logger = setup_logging()

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Verify user exists
        cursor.execute(
            "SELECT user_id, username, display_name, is_active "
            "FROM app_user WHERE user_id = %s",
            (user_id,),
        )
        user = cursor.fetchone()
        if not user:
            click.echo(f"ERROR: User with user_id={user_id} not found.")
            sys.exit(1)

        if user["is_active"] == "N":
            click.echo(f"User '{user['username']}' (user_id={user_id}) is already disabled.")
            return

        if not click.confirm(
            f"Disable user '{user['username']}' ({user['display_name']})? "
            f"This will revoke all active sessions."
        ):
            click.echo("Aborted.")
            return

        # Disable user
        cursor.execute(
            "UPDATE app_user SET is_active = 'N' WHERE user_id = %s",
            (user_id,),
        )

        # Revoke all active sessions
        cursor.execute(
            "UPDATE app_session SET revoked_at = NOW(), revoked_reason = 'account_disabled' "
            "WHERE user_id = %s AND revoked_at IS NULL",
            (user_id,),
        )
        sessions_revoked = cursor.rowcount

        conn.commit()

        click.echo(
            f"Disabled user '{user['username']}' (user_id={user_id}). "
            f"{sessions_revoked} session(s) revoked."
        )

    except Exception as e:
        conn.rollback()
        logger.exception("Failed to disable user")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@click.command("enable-user")
@click.option("--user-id", required=True, type=int, help="User ID to enable")
def enable_user(user_id):
    """Enable a previously disabled user account.

    Examples:
        python main.py admin enable-user --user-id 5
    """
    logger = setup_logging()

    from db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Verify user exists
        cursor.execute(
            "SELECT user_id, username, display_name, is_active "
            "FROM app_user WHERE user_id = %s",
            (user_id,),
        )
        user = cursor.fetchone()
        if not user:
            click.echo(f"ERROR: User with user_id={user_id} not found.")
            sys.exit(1)

        if user["is_active"] == "Y":
            click.echo(f"User '{user['username']}' (user_id={user_id}) is already enabled.")
            return

        # Enable user and reset lockout
        cursor.execute(
            "UPDATE app_user SET is_active = 'Y', failed_login_attempts = 0, "
            "locked_until = NULL WHERE user_id = %s",
            (user_id,),
        )
        conn.commit()

        click.echo(f"Enabled user '{user['username']}' (user_id={user_id}).")

    except Exception as e:
        conn.rollback()
        logger.exception("Failed to enable user")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


@click.command("reset-password")
@click.option("--user-id", required=True, type=int, help="User ID to reset password for")
def reset_password(user_id):
    """Reset a user's password and force change on next login.

    Generates a random temporary password, revokes all sessions, and
    sets force_password_change so the user must pick a new password.

    Examples:
        python main.py admin reset-password --user-id 5
    """
    logger = setup_logging()

    from db.connection import get_connection
    from utils.password import hash_password

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Verify user exists
        cursor.execute(
            "SELECT user_id, username, display_name "
            "FROM app_user WHERE user_id = %s",
            (user_id,),
        )
        user = cursor.fetchone()
        if not user:
            click.echo(f"ERROR: User with user_id={user_id} not found.")
            sys.exit(1)

        if not click.confirm(
            f"Reset password for '{user['username']}' ({user['display_name']})? "
            f"This will revoke all active sessions."
        ):
            click.echo("Aborted.")
            return

        # Generate and hash temp password
        temp_password = secrets.token_urlsafe(12)
        password_hash = hash_password(temp_password)

        # Update password and force change
        cursor.execute(
            "UPDATE app_user SET password_hash = %s, force_password_change = 'Y', "
            "failed_login_attempts = 0, locked_until = NULL "
            "WHERE user_id = %s",
            (password_hash, user_id),
        )

        # Revoke all active sessions
        cursor.execute(
            "UPDATE app_session SET revoked_at = NOW(), revoked_reason = 'password_reset' "
            "WHERE user_id = %s AND revoked_at IS NULL",
            (user_id,),
        )

        conn.commit()

        click.echo(f"Password reset for user '{user['username']}' (user_id={user_id})")
        click.echo(f"Temporary password: {temp_password}")
        click.echo("User will be required to change password on next login.")

    except Exception as e:
        conn.rollback()
        logger.exception("Failed to reset password")
        click.echo(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()
