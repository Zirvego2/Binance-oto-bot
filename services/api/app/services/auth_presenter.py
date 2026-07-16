"""AdminOut donusum yardimcilari."""

from __future__ import annotations

from shared.db import Admin
from shared.membership import is_membership_active, membership_days_remaining

from ..schemas.auth import AdminOut


def admin_to_out(admin: Admin) -> AdminOut:
    return AdminOut.model_validate(admin).model_copy(
        update={
            "membership_days_remaining": membership_days_remaining(admin),
            "membership_active": is_membership_active(admin),
        }
    )
