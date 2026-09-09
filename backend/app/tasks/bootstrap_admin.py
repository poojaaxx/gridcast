"""CLI: idempotently create the first admin user from
GRIDCAST_ADMIN_USERNAME / GRIDCAST_ADMIN_PASSWORD.

This runs automatically on every backend startup (see app.main.on_startup),
so you normally don't need to invoke this manually - it's provided for local
development without Docker, or to bootstrap an admin without restarting the
server.

    python -m app.tasks.bootstrap_admin

Set the two environment variables first (e.g. in .env):

    GRIDCAST_ADMIN_USERNAME=admin
    GRIDCAST_ADMIN_PASSWORD=<a strong password>

The password is hashed with Argon2id before storage and is never logged or
printed by this command.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.services.auth_service import bootstrap_admin

logger = get_logger(__name__)


def main() -> None:
    if not settings.admin_bootstrap_username or not settings.admin_bootstrap_password:
        raise SystemExit(
            "GRIDCAST_ADMIN_USERNAME and GRIDCAST_ADMIN_PASSWORD must both be set "
            "(in .env or the environment) before running this command."
        )

    with session_scope() as db:
        admin = bootstrap_admin(db)
        if admin is not None:
            logger.info("Created admin user '%s'.", admin.username)
        else:
            logger.info(
                "User '%s' already exists - bootstrap is idempotent, nothing to do.",
                settings.admin_bootstrap_username,
            )


if __name__ == "__main__":
    main()
