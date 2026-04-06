import random

from .constants import (
    _DEFAULT_RANDOM_MAX,
    _DEFAULT_RANDOM_MIN,
    _INT_RE,
    _RANDOM_CHOICE_ALIASES,
    _RANDOM_NAME_ALIASES,
    _RANDOM_NUMBER_ALIASES,
)


def parse_random_spec(name: str) -> tuple[int | None, int | None, int] | None:
    raw_name = name.strip()
    if not raw_name:
        return None

    parts = [part.strip() for part in raw_name.split(".")]
    if len(parts) < 2 or parts[0].lower() not in _RANDOM_NAME_ALIASES:
        return None
    if parts[1].lower() not in _RANDOM_NUMBER_ALIASES:
        return None
    if len(parts) > 2 and any(not part for part in parts[2:]):
        return None
    raw_args = ",".join(parts[2:])

    if not raw_args:
        return (None, None, 1)

    parts = [part.strip() for part in raw_args.split(",")]
    if not parts or any(not part or _INT_RE.fullmatch(part) is None for part in parts):
        return None

    numbers = [int(part) for part in parts]
    if len(numbers) == 1:
        low, high, step = 0, numbers[0], 1
    elif len(numbers) == 2:
        low, high = numbers
        step = 1
    elif len(numbers) == 3:
        low, high, step = numbers
        if step == 0:
            return None
    else:
        return None

    if step < 0:
        step = -step
    return min(low, high), max(low, high), step


def parse_random_choice_spec(name: str) -> str | None:
    raw_name = name.strip()
    if not raw_name:
        return None

    parts = [part.strip() for part in raw_name.split(".")]
    if len(parts) < 3:
        return None
    if parts[0].lower() not in _RANDOM_NAME_ALIASES:
        return None
    if parts[1].lower() not in _RANDOM_CHOICE_ALIASES:
        return None

    target = ".".join(parts[2:]).strip()
    if not target:
        return None
    return target


def is_random_match(name: str, segment: str) -> bool:
    spec = parse_random_spec(name)
    if spec is None or _INT_RE.fullmatch(segment) is None:
        return False

    low, high, step = spec
    value = int(segment)
    if low is None or high is None:
        return True
    if not (low <= value <= high):
        return False
    return (value - low) % step == 0


def render_random_number(name: str) -> str | None:
    spec = parse_random_spec(name)
    if spec is None:
        return None

    low, high, step = spec
    if low is None or high is None:
        low, high, step = _DEFAULT_RANDOM_MIN, _DEFAULT_RANDOM_MAX, 1

    candidates = list(range(low, high + 1, step))
    if not candidates:
        return ""
    return str(random.choice(candidates))


def render_random_choice(name: str, variables: dict[str, str]) -> str | None:
    target = parse_random_choice_spec(name)
    if target is None:
        return None

    raw_value = variables.get(target)
    if raw_value is None:
        return None

    items = [item.strip() for item in raw_value.split("||") if item.strip()]
    if not items:
        return ""
    return random.choice(items)


class RandomTemplate:
    @staticmethod
    def parse_spec(spec: str) -> tuple[int | None, int | None, int] | None:
        return parse_random_spec(spec)

    @staticmethod
    def parse_choice(spec: str) -> str | None:
        return parse_random_choice_spec(spec)

    @staticmethod
    def match(spec: str, segment: str) -> bool:
        return is_random_match(spec, segment)

    @staticmethod
    def render(spec: str) -> str | None:
        return render_random_number(spec)

    @staticmethod
    def render_choice(spec: str, variables: dict[str, str]) -> str | None:
        return render_random_choice(spec, variables)
