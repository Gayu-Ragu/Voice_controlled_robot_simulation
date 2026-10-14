import argparse
import math
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

from voice_robot_control.command_parser import get_leak_result, parse_commands
from voice_robot_control.machines import (
    HOME_POSE,
    MACHINE_LOCATIONS,
    MACHINES,
    VALID_MACHINE_IDS,
)
from voice_robot_control.status_lights import StatusLightController


def quaternion_to_yaw(q):
    siny_cosp = 2 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class VoiceCommandNode(Node):
    def __init__(self, text_mode: bool = False):
        super().__init__("voice_command_node")
        self.text_mode = text_mode
        self.publisher = self.create_publisher(Twist, "/cmd_vel", 10)
        self.result_pub = self.create_publisher(String, "/inspection_result", 10)
        self.odom_sub = self.create_subscription(
            Odometry, "/odom", self._odom_callback, 10
        )
        self.x = None
        self.y = None
        self.theta = None
        self.transcriber = None
        self.status_lights = StatusLightController(self)
        # Connect to Gazebo so lights can turn green/red after inspection
        self.status_lights.wait_for_gazebo(timeout=15.0)

        if not self.text_mode:
            from voice_robot_control.transcriber import Transcriber

            self.transcriber = Transcriber()
            self.get_logger().info(
                "Voice mode ready. Press Enter to speak, Ctrl+C to quit."
            )
        else:
            self.get_logger().info(
                "Text mode ready. Type commands (e.g. 'inspect machine 2'), Ctrl+C to quit."
            )
        self.get_logger().info(
            "Look for YELLOW beacon/board on each machine. "
            "After inspect it turns GREEN (OK) or RED (leak + puddle)."
        )

    def _odom_callback(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y
        self.theta = quaternion_to_yaw(msg.pose.pose.orientation)

    def publish_twist(self, linear=0.0, angular=0.0, duration=1.5):
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        end_time = time.time() + duration
        while time.time() < end_time and rclpy.ok():
            self.publisher.publish(msg)
            rclpy.spin_once(self, timeout_sec=0.05)
            time.sleep(0.05)
        self.publisher.publish(Twist())

    def wait_for_odom(self, timeout=10.0):
        start = time.time()
        while rclpy.ok() and self.x is None and (time.time() - start) < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)
        return self.x is not None

    def go_to(self, target_x, target_y, tolerance=0.25, timeout=40.0):
        if not self.wait_for_odom():
            self.get_logger().error("No /odom yet — is the simulation running?")
            return False

        start_time = time.time()
        twist = Twist()
        while rclpy.ok() and (time.time() - start_time) < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)
            dx = target_x - self.x
            dy = target_y - self.y
            distance = math.hypot(dx, dy)
            if distance < tolerance:
                break

            angle_to_goal = math.atan2(dy, dx)
            angle_diff = math.atan2(
                math.sin(angle_to_goal - self.theta),
                math.cos(angle_to_goal - self.theta),
            )

            if abs(angle_diff) > 0.15:
                twist.linear.x = 0.0
                twist.angular.z = 0.7 if angle_diff > 0 else -0.7
            else:
                twist.linear.x = min(0.18, max(0.08, distance * 0.5))
                twist.angular.z = 0.4 * angle_diff

            self.publisher.publish(twist)

        self.publisher.publish(Twist())
        reached = math.hypot(target_x - self.x, target_y - self.y) < tolerance * 1.5
        if not reached:
            self.get_logger().warn(
                f"Timeout approaching ({target_x:.2f}, {target_y:.2f}); "
                f"stopped at ({self.x:.2f}, {self.y:.2f})"
            )
        return reached

    def _react_leak_detected(self):
        for _ in range(3):
            self.publish_twist(angular=2.0, duration=0.35)
            self.publish_twist(angular=-2.0, duration=0.35)
        self.publisher.publish(Twist())

    def _react_no_leak(self):
        # ~full spin in place
        self.publish_twist(angular=1.0, duration=2 * math.pi)
        self.publisher.publish(Twist())

    def do_inspect(self, machine_id: int):
        if machine_id not in VALID_MACHINE_IDS:
            self.get_logger().warn(
                f"Unknown machine {machine_id}. Valid: {sorted(VALID_MACHINE_IDS)}"
            )
            return

        info = MACHINES[machine_id]
        target = MACHINE_LOCATIONS[machine_id]
        self.get_logger().info(
            f"Heading to {info['name']} (#{info['label']}) at {target}..."
        )
        self.go_to(*target)
        leak = get_leak_result(machine_id)

        # Update machine display in Gazebo: green OK / red leak + puddle
        self.status_lights.show_inspection_result(machine_id, leak)

        if leak:
            self._react_leak_detected()
        else:
            self._react_no_leak()

        banner = "LEAKAGE DETECTED" if leak else "No leakage detected"
        result = f"machine_{machine_id}:{banner}"
        self.result_pub.publish(String(data=result))
        print("\n" + "=" * 50)
        print(f" MACHINE {machine_id} ({info['name']}): {banner}")
        if leak:
            print("  → Look at the RED light + red puddle on the machine")
        else:
            print("  → Look at the GREEN light on the machine")
        print("=" * 50 + "\n")

        # Return to spawn / home after analysis
        self.get_logger().info(f"Returning home to {HOME_POSE}...")
        self.go_to(*HOME_POSE, timeout=50.0)
        self.get_logger().info("Back at home position.")


    def handle_command(self, cmd: dict):
        if cmd["type"] == "move":
            d = cmd["direction"]
            if d == "left":
                self.publish_twist(angular=1.0, duration=1.5)
            elif d == "right":
                self.publish_twist(angular=-1.0, duration=1.5)
            elif d == "forward":
                self.publish_twist(linear=0.15, duration=1.5)
            elif d == "backward":
                self.publish_twist(linear=-0.15, duration=1.5)
        elif cmd["type"] == "stop":
            self.publisher.publish(Twist())
        elif cmd["type"] == "inspect":
            self.do_inspect(cmd["machine_id"])
        else:
            self.get_logger().warn(f"Didn't understand: '{cmd.get('raw', '')}'")

    def _read_input(self) -> str:
        if self.text_mode:
            return input("\nType a command > ").strip()

        input("\nPress Enter, then speak your command...")
        audio = self.transcriber.record()
        return self.transcriber.transcribe(audio)

    def run_loop(self):
        while rclpy.ok():
            try:
                text = self._read_input()
            except EOFError:
                break
            commands = parse_commands(text)
            if not commands:
                self.get_logger().warn("Didn't catch anything usable — try again.")
                continue
            for cmd in commands:
                self.handle_command(cmd)


def main(args=None):
    parser = argparse.ArgumentParser(description="Voice / text robot command node")
    parser.add_argument(
        "--text",
        action="store_true",
        help="Type commands instead of using the microphone",
    )
    known, _ = parser.parse_known_args(args=args)

    rclpy.init(args=args)
    node = VoiceCommandNode(text_mode=known.text)
    try:
        node.run_loop()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
