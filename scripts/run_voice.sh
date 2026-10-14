#!/usr/bin/env bash
# Run voice (or --text) command node against a running sim.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck disable=SC1091
source "${HOME}/miniforge3/etc/profile.d/conda.sh"
conda activate ros_env

# shellcheck disable=SC1091
source "${ROOT}/install/setup.bash"

MODE="${1:-}"
if [[ "${MODE}" == "--text" ]]; then
  echo "Starting text command mode..."
  exec ros2 run voice_robot_control voice_command_node -- --text
fi

echo "Starting voice command mode (Whisper)..."
exec ros2 run voice_robot_control voice_command_node
