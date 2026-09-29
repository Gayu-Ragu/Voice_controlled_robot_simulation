import re
import random

LEAK_RESULTS = {1: False, 2: True, 3: True, 4: False}

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

NUMBER_WORDS = {
    "one": 1, "won": 1,
    "two": 2, "too": 2, "to": 2,
    "three": 3, "free": 3, "tree": 3,
    "four": 4, "for": 4, "fore": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

MACHINE_PATTERN = re.compile(
    r"\b(?:machine|mission)\s*(\d+|one|won|two|too|three|free|tree|four|for|fore|five|six|seven|eight|nine|ten)\b"
)

def _looks_like_garbage(text: str) -> bool:
    return bool(re.search(r"[^\x00-\x7F]", text))

def parse_commands(text: str):
    if _looks_like_garbage(text):
        return []

    t = text.lower().strip()
    if not t:
        return []

    if re.search(r"\bstop\b", t):
        return [{"type": "stop"}]

    m = MACHINE_PATTERN.search(t)
    if m and re.search(r"\b(check|inspect|leak)\w*\b", t):
        raw = m.group(1)
        machine_id = int(raw) if raw.isdigit() else NUMBER_WORDS.get(raw)
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
    if machine_id in LEAK_RESULTS:
        return LEAK_RESULTS[machine_id]
    return random.choice([True, False])
