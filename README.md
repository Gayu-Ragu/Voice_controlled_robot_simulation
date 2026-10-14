# Voice Robot Control

Voice- (or text-) controlled TurtleBot3 that inspects three factory machines for simulated leakage.

## RoboStack setup (this machine)

ROS 2 Humble lives in conda env `ros_env` — **not** `/opt/ros`.

```bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate ros_env
cd ~/ros2_ws
colcon build --packages-select voice_robot_control
source install/setup.bash
```

## Run the demo

**Terminal 1 — simulation**

```bash
conda activate ros_env
source ~/ros2_ws/install/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 launch voice_robot_control factory_sim.launch.py
# or: bash src/voice_robot_control/scripts/run_sim.sh
```

**Terminal 2 — commands**

```bash
conda activate ros_env
source ~/ros2_ws/install/setup.bash

# Typed commands (no mic / no Whisper download needed):
ros2 run voice_robot_control voice_command_node -- --text

# Or real voice (Whisper base, auto mic):
ros2 run voice_robot_control voice_command_node
```

### Example commands

| Say / type | Effect |
|------------|--------|
| `inspect machine 1` | Drive to machine 1 → no leak (spin) |
| `go to machine 2` | Drive to machine 2 → leak (wiggle) |
| `check machine 3` | Drive to machine 3 → leak |
| `forward` / `left` / `right` / `backward` | Short move |
| `stop` | Stop |

## Machines & status lights

| ID | Body color | Pose | Leak? |
|----|------------|------|-------|
| 1 | Blue (1 block) | (2.5, 1.5) | No |
| 2 | Orange (2 blocks) | (2.5, −1.5) | Yes |
| 3 | Green body (3 blocks) | (−2.5, 0) | Yes |

**Status light on each machine pole:**

| Light | Meaning |
|-------|---------|
| **Yellow** | Not inspected yet |
| **Green** | Inspected — no leak |
| **Red** (+ red puddle) | Inspected — leakage detected |

After `inspect machine N`, watch the sphere on that machine change color in Gazebo.

Inspection results are also published on `/inspection_result`.

## Useful env vars

| Variable | Meaning |
|----------|---------|
| `VOICE_ASR_MODEL` | Hugging Face model (default `openai/whisper-base`) |
| `VOICE_ASR_DEVICE` | `-1` = CPU, `0` = first GPU |
| `VOICE_MIC_DEVICE` | Force sounddevice input index |
| `TURTLEBOT3_MODEL` | `burger` (default), `waffle`, … |

## Jetson Nano note

Keep `openai/whisper-base` or drop to `openai/whisper-tiny.en` if memory is tight. Prefer text mode for bring-up.
