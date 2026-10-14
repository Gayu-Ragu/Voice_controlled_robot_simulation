"""Shared factory-machine definitions for sim world + voice navigation."""

# TurtleBot3 spawn / return-home pose in factory_sim.launch.py
HOME_POSE = (0.0, 0.0)

# Visual model pose = where the machine sits in Gazebo.
# approach = where the robot drives to (in front of the machine, clear of collision).
MACHINES = {
    1: {
        "name": "machine_1",
        "label": "1",
        "pose": (2.5, 1.5),
        "approach": (1.7, 1.5),
        "leak": False,
        "color": (0.2, 0.4, 0.9),  # blue
    },
    2: {
        "name": "machine_2",
        "label": "2",
        "pose": (2.5, -1.5),
        "approach": (1.7, -1.5),
        "leak": True,
        "color": (0.9, 0.45, 0.1),  # orange
    },
    3: {
        "name": "machine_3",
        "label": "3",
        "pose": (-2.5, 0.0),
        "approach": (-1.7, 0.0),
        "leak": True,
        "color": (0.2, 0.7, 0.3),  # green
    },
}

MACHINE_LOCATIONS = {mid: data["approach"] for mid, data in MACHINES.items()}
LEAK_RESULTS = {mid: data["leak"] for mid, data in MACHINES.items()}
VALID_MACHINE_IDS = frozenset(MACHINES.keys())
