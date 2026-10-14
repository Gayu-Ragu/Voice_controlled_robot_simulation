from voice_robot_control.command_parser import get_leak_result, parse_commands


def test_inspect_commands():
    assert parse_commands("check machine 1") == [
        {"type": "inspect", "machine_id": 1}
    ]
    assert parse_commands("go to machine two") == [
        {"type": "inspect", "machine_id": 2}
    ]
    assert parse_commands("inspect machine 3") == [
        {"type": "inspect", "machine_id": 3}
    ]


def test_invalid_machine_rejected():
    assert parse_commands("check machine 4")[0]["type"] == "unknown"


def test_move_and_stop():
    assert parse_commands("go forward") == [{"type": "move", "direction": "forward"}]
    assert parse_commands("stop") == [{"type": "stop"}]


def test_leak_map():
    assert get_leak_result(1) is False
    assert get_leak_result(2) is True
    assert get_leak_result(3) is True
