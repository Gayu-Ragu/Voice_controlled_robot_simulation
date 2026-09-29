import time
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

from voice_robot_control.transcriber import Transcriber
from voice_robot_control.command_parser import parse_commands, get_leak_result

MACHINE_LOCATIONS = {
    1: (2.0, 0.0),
    2: (0.0, 2.0),
    3: (-2.0, 0.0),
    4: (0.0, -2.0),
}

def quaternion_to_yaw(q):
    siny_cosp = 2 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)

class VoiceCommandNode(Node):
    def __init__(self):
        super().__init__("voice_command_node")
        self.publisher = self.create_publisher(Twist, "/cmd_vel", 10)
        self.odom_sub = self.create_subscription(Odometry, "/odom", self._odom_callback, 10)
        self.x = None
        self.y = None
        self.theta = None
        self.transcriber = Transcriber()
        self.get_logger().info("Ready. Press Enter to speak a command, Ctrl+C to quit.")

    def _odom_callback(self, msg):
        self.x = msg.pose.pose.position.x
        self.y = msg.pose.pose.position.y
        self.theta = quaternion_to_yaw(msg.pose.pose.orientation)

    def publish_twist(self, linear=0.0, angular=0.0, duration=1.5):
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        end_time = time.time() + duration
        while time.time() < end_time:
            self.publisher.publish(msg)
            time.sleep(0.1)
        self.publisher.publish(Twist())

    def go_to(self, target_x, target_y, tolerance=0.2, timeout=25.0):
        start_time = time.time()
        twist = Twist()
        while rclpy.ok() and (time.time() - start_time) < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.x is None:
                continue

            dx = target_x - self.x
            dy = target_y - self.y
            distance = math.sqrt(dx * dx + dy * dy)
            if distance < tolerance:
                break

            angle_to_goal = math.atan2(dy, dx)
            angle_diff = angle_to_goal - self.theta
            angle_diff = math.atan2(math.sin(angle_diff), math.cos(angle_diff))

            if abs(angle_diff) > 0.1:
                twist.linear.x = 0.0
                twist.angular.z = 0.8 if angle_diff > 0 else -0.8
            else:
                twist.linear.x = min(0.15, distance)
                twist.angular.z = 0.0

            self.publisher.publish(twist)

        self.publisher.publish(Twist())

    def _react_leak_detected(self):
        for _ in range(3):
            self.publish_twist(angular=2.0, duration=0.4)
            self.publish_twist(angular=-2.0, duration=0.4)
        self.publisher.publish(Twist())

    def _react_no_leak(self):
        self.publish_twist(angular=1.0, duration=2 * math.pi)
        self.publisher.publish(Twist())

    def do_inspect(self, machine_id: int):
        target = MACHINE_LOCATIONS.get(machine_id, (1.0, 1.0))
        self.get_logger().info(f"Heading to machine {machine_id} at {target}...")
        self.go_to(*target)
        leak = get_leak_result(machine_id)

        if leak:
            self._react_leak_detected()
        else:
            self._react_no_leak()

        banner = "!!! LEAKAGE DETECTED !!!" if leak else "No leakage detected."
        print("\n" + "=" * 50)
        print(f" MACHINE {machine_id} INSPECTION RESULT: {banner}")
        print("=" * 50 + "\n")

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

    def run_loop(self):
        while rclpy.ok():
            input("\nPress Enter, then speak your command...")
            audio = self.transcriber.record()
            text = self.transcriber.transcribe(audio)
            commands = parse_commands(text)
            if not commands:
                self.get_logger().warn("Didn't catch anything usable — try again.")
                continue
            for cmd in commands:
                self.handle_command(cmd)

def main():
    rclpy.init()
    node = VoiceCommandNode()
    try:
        node.run_loop()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
