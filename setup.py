import os
from glob import glob

from setuptools import find_packages, setup

package_name = "voice_robot_control"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml", "README.md"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "worlds"), glob("worlds/*")),
        (os.path.join("share", package_name, "scripts"), glob("scripts/*")),
        (
            os.path.join("share", package_name, "models", "machine_1"),
            glob("models/machine_1/*"),
        ),
        (
            os.path.join("share", package_name, "models", "machine_2"),
            glob("models/machine_2/*"),
        ),
        (
            os.path.join("share", package_name, "models", "machine_3"),
            glob("models/machine_3/*"),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="gayathri",
    maintainer_email="gayathri@todo.todo",
    description="Voice-controlled robot with factory machine leak inspection",
    license="Apache-2.0",
    extras_require={"test": ["pytest"]},
    entry_points={
        "console_scripts": [
            "voice_command_node = voice_robot_control.voice_command_node:main",
        ],
    },
)
