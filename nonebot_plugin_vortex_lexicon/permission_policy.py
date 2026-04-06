from nonebot import get_driver
from nonebot.adapters import Event

PERMISSION_ALL = "all"
PERMISSION_ADMIN = "admin"
PERMISSION_OWNER = "owner"
PERMISSION_SUPERUSER = "superuser"
PERMISSION_ALLOWLIST_ADMIN = "allowlist_admin"


def normalize_permission(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return PERMISSION_ALL

    aliases = {
        "all": PERMISSION_ALL,
        "全部": PERMISSION_ALL,
        "所有人": PERMISSION_ALL,
        "admin": PERMISSION_ADMIN,
        "管理员": PERMISSION_ADMIN,
        "owner": PERMISSION_OWNER,
        "群主": PERMISSION_OWNER,
        "superuser": PERMISSION_SUPERUSER,
        "超管": PERMISSION_SUPERUSER,
        "allowlist_admin": PERMISSION_ALLOWLIST_ADMIN,
        "allowlist": PERMISSION_ALLOWLIST_ADMIN,
        "白名单管理": PERMISSION_ALLOWLIST_ADMIN,
        "指定成员+管理员+群主+超管": PERMISSION_ALLOWLIST_ADMIN,
    }
    return aliases.get(value, PERMISSION_ALL)


def normalize_allow_users(raw: str | None) -> str:
    if not raw:
        return ""
    normalized = raw.replace("，", ",").replace("|", ",")
    items = [item.strip() for item in normalized.split(",") if item.strip()]
    user_ids = sorted({int(item) for item in items if item.isdigit()})
    return "|".join(str(user_id) for user_id in user_ids)


def parse_allow_users(raw: str | None) -> set[int]:
    if not raw:
        return set()
    normalized = raw.replace("，", ",").replace("|", ",")
    items = [item.strip() for item in normalized.split(",") if item.strip()]
    return {int(item) for item in items if item.isdigit()}


def get_superusers() -> set[int]:
    values = getattr(get_driver().config, "superusers", set())
    return {int(item) for item in values if str(item).isdigit()}


def resolve_group_role(event: Event) -> str | None:
    data = getattr(event, "data", None)
    member = getattr(data, "group_member", None) if data is not None else None
    role = getattr(member, "role", None)
    return role if isinstance(role, str) else None


def can_use_entry(event: Event, permission: str, allow_users: str) -> bool:
    try:
        user_id_str = event.get_user_id()
    except Exception:
        return False

    if not user_id_str.isdigit():
        return False
    user_id = int(user_id_str)

    if user_id in get_superusers():
        return True

    normalized_permission = normalize_permission(permission)
    if normalized_permission == PERMISSION_ALL:
        return True
    if normalized_permission == PERMISSION_SUPERUSER:
        return False

    role = resolve_group_role(event)
    is_admin_or_owner = role in {"admin", "owner"}
    is_owner = role == "owner"

    if normalized_permission == PERMISSION_ADMIN:
        return is_admin_or_owner
    if normalized_permission == PERMISSION_OWNER:
        return is_owner
    if normalized_permission == PERMISSION_ALLOWLIST_ADMIN:
        if user_id in parse_allow_users(allow_users):
            return True
        return is_admin_or_owner
    return True

