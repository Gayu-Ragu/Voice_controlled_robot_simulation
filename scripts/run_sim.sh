#!/usr/bin/env bash
# Launch factory sim (3 machines + TurtleBot3) using RoboStack ros_env.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck disable=SC1091
source "${HOME}/miniforge3/etc/profile.d/conda.sh"
conda activate ros_env

export TURTLEBOT3_MODEL="${TURTLEBOT3_MODEL:-burger}"
# shellcheck disable=SC1091
source "${ROOT}/install/setup.bash"

echo "Starting factory sim (machines 1–3 + TurtleBot3 ${TURTLEBOT3_MODEL})..."
exec ros2 launch voice_robot_control factory_sim.launch.py
