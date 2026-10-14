import re

from voice_robot_control.machines import LEAK_RESULTS, VALID_MACHINE_IDS

DIRECTION_PATTERN = re.compile(
    r"\b(left|lift|right|night|forward|ahead|back(?:ward)?)\b"
)

DIRECTION_MAP = {
    "left": "left",
    "lift": "left",
    "right": "right",
    "night": "right",
    "forward": "forward",
    "ahead": "forward",
    "back": "backward",
    "backward": "backward",
}

# Only machines 1–3 exist in the factory sim
NUMBER_WORDS = {
    "one": 1, "won": 1,
    "two": 2, "too": 2, "to": 2,
    "three": 3, "free": 3, "tree": 3,
}

MACHINE_PATTERN = re.compile(
    r"\b(?:machine|mission)\s*"
    r"(1|2|3|one|won|two|too|to|three|free|tree)\b"
)

# "check / inspect / go to / visit machine N"
INSPECT_PATTERN = re.compile(
    r"\b(check|inspect|leak|visit|examine|go\s+to|head\s+to)\w*\b"
)


def _looks_like_garbage(text: str) -> bool:
    return bool(re.search(r"[^\x00-\x7F]", text))


def _parse_machine_id(raw: str):
    if raw.isdigit():
        mid = int(raw)
    else:
        mid = NUMBER_WORDS.get(raw)
    if mid in VALID_MACHINE_IDS:
        return mid
    return None


def parse_commands(text: str):
    if _looks_like_garbage(text):
        return []

    t = text.lower().strip()
    if not t:
        return []

    if re.search(r"\bstop\b", t):
        return [{"type": "stop"}]

    m = MACHINE_PATTERN.search(t)
    if m and INSPECT_PATTERN.search(t):
        machine_id = _parse_machine_id(m.group(1))
        if machine_id is not None:
            return [{"type": "inspect", "machine_id": machine_id}]
        return [{"type": "unknown", "raw": text}]

    # Bare "machine 2" also counts as inspect
    if m:
        machine_id = _parse_machine_id(m.group(1))
        if machine_id is not None:
            return [{"type": "inspect", "machine_id": machine_id}]

    commands = []
    for match in DIRECTION_PATTERN.finditer(t):
        direction = DIRECTION_MAP.get(match.group(1))
        if direction:
            commands.append({"type": "move", "direction": direction})

    if not commands:
        return [{"type": "unknown", "raw": text}]

    return commands


def get_leak_result(machine_id: int) -> bool:
    return bool(LEAK_RESULTS.get(machine_id, False))
