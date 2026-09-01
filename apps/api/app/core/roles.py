"""RBAC foundation (Tier 1) — a fixed, stored role per user, replacing the
previously-only email-allowlist admin check with something that can express
more than "admin or not." See docs/APARIX_TIER1_AUDIT.md for why this is
scoped to the backend only this session (no role-editing UI yet).

Deliberately a plain string column with a fixed set of values, not a
separate roles/permissions table — six roles, no per-permission grid, no
dynamic role creation. See core/deps.py::require_role() for how routes use
this.
"""

from typing import Final


class Role:
    SUPER_ADMIN: Final = "super_admin"
    ADMIN: Final = "admin"
    COMPLIANCE: Final = "compliance"
    ANALYST: Final = "analyst"
    SUPPORT: Final = "support"
    USER: Final = "user"


ALL_ROLES: Final[tuple[str, ...]] = (
    Role.SUPER_ADMIN,
    Role.ADMIN,
    Role.COMPLIANCE,
    Role.ANALYST,
    Role.SUPPORT,
    Role.USER,
)

DEFAULT_ROLE: Final = Role.USER
