"""Update Gazebo status overlays on each machine after inspection.

Machines already show a yellow beacon/board in their SDF.
After inspect we spawn a LARGE green or red overlay (+ puddle if leak)
so the result is obvious in the GUI.
"""

from __future__ import annotations

import time

from gazebo_msgs.srv import DeleteEntity, SpawnEntity
from geometry_msgs.msg import Pose
from rclpy.node import Node

from voice_robot_control.machines import MACHINES

# Overlay sits above the built-in yellow beacon
OVERLAY_Z = 1.45

GAZEBO_MAT = {
    "ok": "Gazebo/Green",
    "leak": "Gazebo/Red",
}


def _overlay_sdf(model_name: str, material: str) -> str:
    """Huge sphere + front board — hard to miss."""
    return f"""<?xml version="1.0"?>
<sdf version="1.6">
  <model name="{model_name}">
    <static>true</static>
    <link name="link">
      <visual name="beacon">
        <pose>0 0 0 0 0 0</pose>
        <geometry><sphere><radius>0.28</radius></sphere></geometry>
        <material>
          <script>
            <uri>file://media/materials/scripts/gazebo.material</uri>
            <name>{material}</name>
          </script>
        </material>
      </visual>
      <visual name="cap">
        <pose>0 0 0.35 0 0 0</pose>
        <geometry><cylinder><radius>0.2</radius><length>0.12</length></cylinder></geometry>
        <material>
          <script>
            <uri>file://media/materials/scripts/gazebo.material</uri>
            <name>{material}</name>
          </script>
        </material>
      </visual>
    </link>
  </model>
</sdf>
"""


def _board_sdf(model_name: str, material: str, facing: str) -> str:
    """Large status plate covering the yellow board on the machine."""
    if facing == "neg_x":
        # machines 1 & 2 (on +X side): board faces arena center
        pose = "-0.36 0 0 0 0 0"
        size = "0.1 0.5 0.4"
    else:
        # machine 3 (on -X side): board faces arena center
        pose = "0.36 0 0 0 0 0"
        size = "0.1 0.5 0.4"
    return f"""<?xml version="1.0"?>
<sdf version="1.6">
  <model name="{model_name}">
    <static>true</static>
    <link name="link">
      <visual name="board">
        <pose>{pose}</pose>
        <geometry><box><size>{size}</size></box></geometry>
        <material>
          <script>
            <uri>file://media/materials/scripts/gazebo.material</uri>
            <name>{material}</name>
          </script>
        </material>
      </visual>
    </link>
  </model>
</sdf>
"""


def _puddle_sdf(model_name: str) -> str:
    return f"""<?xml version="1.0"?>
<sdf version="1.6">
  <model name="{model_name}">
    <static>true</static>
    <link name="link">
      <visual name="puddle">
        <pose>0 0 0.03 0 0 0</pose>
        <geometry><cylinder><radius>0.35</radius><length>0.04</length></cylinder></geometry>
        <material>
          <script>
            <uri>file://media/materials/scripts/gazebo.material</uri>
            <name>Gazebo/Red</name>
          </script>
        </material>
      </visual>
      <visual name="drip1">
        <pose>0.08 0.06 0.18 0 0 0</pose>
        <geometry><sphere><radius>0.07</radius></sphere></geometry>
        <material>
          <script>
            <uri>file://media/materials/scripts/gazebo.material</uri>
            <name>Gazebo/Red</name>
          </script>
        </material>
      </visual>
      <visual name="drip2">
        <pose>-0.06 -0.05 0.28 0 0 0</pose>
        <geometry><sphere><radius>0.05</radius></sphere></geometry>
        <material>
          <script>
            <uri>file://media/materials/scripts/gazebo.material</uri>
            <name>Gazebo/Red</name>
          </script>
        </material>
      </visual>
    </link>
  </model>
</sdf>
"""


def overlay_name(machine_id: int) -> str:
    return f"status_overlay_{machine_id}"


def board_name(machine_id: int) -> str:
    return f"status_board_{machine_id}"


def puddle_name(machine_id: int) -> str:
    return f"leak_puddle_{machine_id}"


class StatusLightController:
    def __init__(self, node: Node):
        self.node = node
        self._spawn = node.create_client(SpawnEntity, "/spawn_entity")
        self._delete = node.create_client(DeleteEntity, "/delete_entity")
        self._ready = False

    def _spin_until(self, future, timeout: float) -> bool:
        deadline = time.time() + timeout
        while not future.done() and time.time() < deadline:
            time.sleep(0.02)
            try:
                import rclpy

                rclpy.spin_once(self.node, timeout_sec=0.02)
            except Exception:
                pass
        return future.done()

    def wait_for_gazebo(self, timeout: float = 20.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if self._spawn.wait_for_service(timeout_sec=0.5) and self._delete.wait_for_service(
                timeout_sec=0.1
            ):
                self._ready = True
                self.node.get_logger().info("Gazebo status overlays connected.")
                return True
            time.sleep(0.2)
        self.node.get_logger().warn(
            "Gazebo spawn/delete not available — overlays disabled "
            "(yellow lights on machines still show 'not inspected')."
        )
        return False

    def _call_delete(self, name: str) -> None:
        if not self._ready:
            return
        req = DeleteEntity.Request()
        req.name = name
        future = self._delete.call_async(req)
        self._spin_until(future, 2.0)

    def _call_spawn(self, name: str, xml: str, x: float, y: float, z: float) -> bool:
        if not self._ready:
            return False
        req = SpawnEntity.Request()
        req.name = name
        req.xml = xml
        req.robot_namespace = ""
        req.initial_pose = Pose()
        req.initial_pose.position.x = float(x)
        req.initial_pose.position.y = float(y)
        req.initial_pose.position.z = float(z)
        req.reference_frame = "world"
        future = self._spawn.call_async(req)
        if not self._spin_until(future, 4.0):
            self.node.get_logger().warn(f"Timed out spawning {name}")
            return False
        result = future.result()
        if result is None or not result.success:
            msg = getattr(result, "status_message", "unknown")
            self.node.get_logger().warn(f"Spawn {name} failed: {msg}")
            return False
        self.node.get_logger().info(f"Spawned visible status marker: {name}")
        return True

    def show_inspection_result(self, machine_id: int, leak: bool) -> None:
        if not self._ready:
            self.wait_for_gazebo(timeout=10.0)
        if not self._ready:
            self.node.get_logger().warn(
                "Cannot spawn green/red overlay. Yellow beacon on the machine "
                "means 'not updated'. Is factory_sim.launch.py running?"
            )
            return

        info = MACHINES[machine_id]
        x, y = info["pose"]
        state = "leak" if leak else "ok"
        mat = GAZEBO_MAT[state]
        facing = "pos_x" if machine_id == 3 else "neg_x"

        # Replace any previous overlay
        for name in (overlay_name(machine_id), board_name(machine_id), puddle_name(machine_id)):
            self._call_delete(name)
        time.sleep(0.15)

        self._call_spawn(overlay_name(machine_id), _overlay_sdf(overlay_name(machine_id), mat), x, y, OVERLAY_Z)
        self._call_spawn(
            board_name(machine_id),
            _board_sdf(board_name(machine_id), mat, facing),
            x,
            y,
            0.7,
        )

        if leak:
            px = x - 0.55 if x > 0 else x + 0.55
            self._call_spawn(puddle_name(machine_id), _puddle_sdf(puddle_name(machine_id)), px, y, 0.0)

        label = "RED = LEAK" if leak else "GREEN = OK"
        self.node.get_logger().info(f"Machine {machine_id} display → {label}")
