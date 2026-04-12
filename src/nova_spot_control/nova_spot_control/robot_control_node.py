import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

class RobotControlNode(Node):
    def __init__(self):
        super().__init__('robot_control_node')

        # Subscribe to commands from voice node
        self.command_subscriber = self.create_subscription(
            String,
            'robot_command',
            self.command_callback,
            10
        )

        # Publish status back to voice node
        self.status_publisher = self.create_publisher(Bool, 'robot_status', 10)

        # Initialize I2C and PCA9685
        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.pca = PCA9685(self.i2c)
            self.pca.frequency = 50

            # Initialize 12 servos for the 4 legs (3 per leg)
            # Example setup: 0-2 (Leg 1), 3-5 (Leg 2), 6-8 (Leg 3), 9-11 (Leg 4)
            self.servos = []
            for i in range(12):
                self.servos.append(servo.Servo(self.pca.channels[i]))

            self.get_logger().info("Hardware initialized successfully.")
        except Exception as e:
            self.get_logger().error(f"Failed to initialize hardware: {e}")
            self.servos = None

        # State tracking
        self.current_state = "stand"  # Assume starting standing or seated, need to track to avoid redundant moves

        self.get_logger().info("Robot Control Node Initialized.")

    def command_callback(self, msg):
        command = msg.data
        self.get_logger().info(f"Received command: {command}")

        if command == "sit":
            self.execute_sit()
        elif command == "stand":
            self.execute_stand()
        elif command == "walk":
            self.execute_walk()
        else:
            self.get_logger().warn(f"Unknown command: {command}")

        # Send ready status back to resume listening
        self.publish_ready_status()

    def publish_ready_status(self):
        msg = Bool()
        msg.data = True
        self.status_publisher.publish(msg)
        self.get_logger().info("Finished executing. Ready for next command.")

    def set_servos(self, angles):
        if self.servos is None:
            self.get_logger().warn("Hardware not initialized, simulating servo movement.")
            return

        # Example angles is a list of 12 angles for each servo.
        for i in range(12):
            if i < len(angles):
                try:
                    self.servos[i].angle = angles[i]
                except ValueError:
                    self.get_logger().error(f"Invalid angle {angles[i]} for servo {i}")

    def execute_sit(self):
        if self.current_state == "sit":
            self.get_logger().info("Already sitting.")
            time.sleep(1) # buffer time
            return

        self.get_logger().info("Executing Sit...")

        # Example angles for sitting. You will need to calibrate these
        # for the specific kinematics of the Nova Mini Spot.
        # Format: [Leg1_Hip, Leg1_Knee, Leg1_Ankle, Leg2_Hip, ...]
        sit_angles = [90, 150, 30] * 4
        self.set_servos(sit_angles)

        time.sleep(2) # Give it time to physically move
        self.current_state = "sit"
        self.get_logger().info("Sit completed.")

    def execute_stand(self):
        if self.current_state == "stand":
            self.get_logger().info("Already standing.")
            time.sleep(1) # buffer time
            return

        self.get_logger().info("Executing Stand...")

        # Example angles for standing
        stand_angles = [90, 90, 90] * 4
        self.set_servos(stand_angles)

        time.sleep(2) # Give it time to physically move
        self.current_state = "stand"
        self.get_logger().info("Stand completed.")

    def execute_walk(self):
        if self.current_state != "stand":
            self.get_logger().info("Must stand first to walk. Standing up...")
            self.execute_stand()
            time.sleep(1)

        self.get_logger().info("Executing Walk (10 steps)...")

        # Simple placeholder walking gait. A real quadruped gait
        # (like a trot or crawl) requires a sequence of coordinated movements.
        # Here we loop through a basic sequence 10 times.
        for step in range(10):
            self.get_logger().info(f"Step {step+1}/10")

            # Lift and move forward legs 1 and 4 (diagonal pairs)
            self.set_servos([90, 60, 90,  90, 90, 90,  90, 90, 90,  90, 60, 90])
            time.sleep(0.2)
            self.set_servos([110, 90, 90,  90, 90, 90,  90, 90, 90,  70, 90, 90])
            time.sleep(0.2)

            # Lift and move forward legs 2 and 3
            self.set_servos([90, 90, 90,  90, 60, 90,  90, 60, 90,  90, 90, 90])
            time.sleep(0.2)
            self.set_servos([90, 90, 90,  110, 90, 90,  70, 90, 90,  90, 90, 90])
            time.sleep(0.2)

        # Return to neutral stand
        self.execute_stand()

        self.get_logger().info("Walk completed.")

def main(args=None):
    rclpy.init(args=args)
    node = RobotControlNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

if __name__ == '__main__':
    main()
