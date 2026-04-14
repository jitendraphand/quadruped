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

            # Channel mapping
            # Front Left:  A(0),  B(1),  C(2)
            # Front Right: A(4),  B(5),  C(6)
            # Back Left:   A(8),  B(9),  C(10)
            # Back Right:  A(12), B(13), C(14)

            # Group them to initialize correctly
            motor_a_channels = [0, 4, 8, 12]
            motor_b_channels = [1, 5, 9, 13]
            motor_c_channels = [2, 6, 10, 14]

            self.servos = {}
            for channel in motor_a_channels + motor_b_channels:
                self.servos[channel] = servo.Servo(
                    self.pca.channels[channel],
                    actuation_range=270,
                    min_pulse=500,
                    max_pulse=2500
                )

            for channel in motor_c_channels:
                self.servos[channel] = servo.Servo(
                    self.pca.channels[channel],
                    actuation_range=180,
                    min_pulse=900,
                    max_pulse=2100
                )

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
        elif command == "turn right":
            self.execute_turn_right()
        else:
            self.get_logger().warn(f"Unknown command: {command}")

        # Send ready status back to resume listening
        self.publish_ready_status()

    def publish_ready_status(self):
        msg = Bool()
        msg.data = True
        self.status_publisher.publish(msg)
        self.get_logger().info("Finished executing. Ready for next command.")

    def clamp_angle(self, channel, angle):
        """Clamp angle based on motor allowed ranges."""
        if channel in [0, 4, 8, 12]:  # Motor A
            return max(67.5, min(202.5, angle))
        elif channel in [1, 5, 9, 13]:  # Motor B
            return max(67.5, min(202.5, angle))
        elif channel in [2, 6, 10, 14]:  # Motor C
            return max(30.0, min(150.0, angle))
        return angle

    def set_servos(self, angle_dict):
        """
        Set multiple servos at once using a dictionary of {channel: angle}.
        Angles will be clamped to safe ranges.
        """
        if self.servos is None:
            self.get_logger().warn("Hardware not initialized, simulating servo movement.")
            return

        for channel, angle in angle_dict.items():
            if channel in self.servos:
                try:
                    safe_angle = self.clamp_angle(channel, angle)
                    self.servos[channel].angle = safe_angle
                except ValueError:
                    self.get_logger().error(f"Invalid angle {angle} for servo {channel}")

    def execute_sit(self):
        if self.current_state == "sit":
            self.get_logger().info("Already sitting.")
            time.sleep(1) # buffer time
            return

        self.get_logger().info("Executing Sit...")

        # Sitting position based on aligned baselines
        # Baseline is A:135, B:135, C:90
        # To sit, we might adjust B (Hip Flexion) and C (Knee)
        # Assuming lowering the knee and extending/flexing hip makes it sit
        sit_angles = {
            # Front Left
            0: 135, 1: 200, 2: 30,
            # Front Right
            4: 135, 5: 200, 6: 30,
            # Back Left
            8: 135, 9: 200, 10: 30,
            # Back Right
            12: 135, 13: 200, 14: 30
        }
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

        # Aligned baseline for standing: A=135, B=135, C=90
        stand_angles = {
            # Front Left
            0: 135, 1: 135, 2: 90,
            # Front Right
            4: 135, 5: 135, 6: 90,
            # Back Left
            8: 135, 9: 135, 10: 90,
            # Back Right
            12: 135, 13: 135, 14: 90
        }
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

        # Basic placeholder gait around new baselines [135, 135, 90]
        for step in range(10):
            self.get_logger().info(f"Step {step+1}/10")

            # Lift legs 1 (Front Left) and 4 (Back Right)
            self.set_servos({
                # Lift 1 & 4 (Motor C slightly bent)
                0: 135, 1: 135, 2: 60,
                4: 135, 5: 135, 6: 90,
                8: 135, 9: 135, 10: 90,
                12: 135, 13: 135, 14: 60
            })
            time.sleep(0.2)

            # Move 1 & 4 forward (Motor B adjusted)
            self.set_servos({
                0: 135, 1: 155, 2: 90,
                4: 135, 5: 135, 6: 90,
                8: 135, 9: 135, 10: 90,
                12: 135, 13: 115, 14: 90
            })
            time.sleep(0.2)

            # Lift legs 2 (Front Right) and 3 (Back Left)
            self.set_servos({
                0: 135, 1: 135, 2: 90,
                4: 135, 5: 135, 6: 60,
                8: 135, 9: 135, 10: 60,
                12: 135, 13: 135, 14: 90
            })
            time.sleep(0.2)

            # Move 2 & 3 forward
            self.set_servos({
                0: 135, 1: 135, 2: 90,
                4: 135, 5: 155, 6: 90,
                8: 135, 9: 115, 10: 90,
                12: 135, 13: 135, 14: 90
            })
            time.sleep(0.2)

        # Return to neutral stand
        self.execute_stand()

        self.get_logger().info("Walk completed.")

    def execute_turn_right(self):
        if self.current_state != "stand":
            self.get_logger().info("Must stand first to turn. Standing up...")
            self.execute_stand()
            time.sleep(1)

        self.get_logger().info("Executing Turn Right...")

        # Turn right rotates 90 deg about vertical axis.
        # This typically involves lifting legs and using Motor A (sideways movement)

        # Step 1: Lift diagonal pair 1 (FL) & 4 (BR) and rotate A
        self.set_servos({
            # Lift (reduce C) and rotate (adjust A)
            0: 165, 1: 135, 2: 60,   # FL
            4: 135, 5: 135, 6: 90,   # FR
            8: 135, 9: 135, 10: 90,  # BL
            12: 105, 13: 135, 14: 60 # BR
        })
        time.sleep(0.3)

        # Step 2: Put down pair 1 & 4
        self.set_servos({
            0: 165, 1: 135, 2: 90,
            4: 135, 5: 135, 6: 90,
            8: 135, 9: 135, 10: 90,
            12: 105, 13: 135, 14: 90
        })
        time.sleep(0.3)

        # Step 3: Lift diagonal pair 2 (FR) & 3 (BL) and rotate A to match, while restoring A for 1 & 4
        self.set_servos({
            0: 135, 1: 135, 2: 90,   # FL restored
            4: 105, 5: 135, 6: 60,   # FR lifted and rotated
            8: 165, 9: 135, 10: 60,  # BL lifted and rotated
            12: 135, 13: 135, 14: 90 # BR restored
        })
        time.sleep(0.3)

        # Step 4: Put down pair 2 & 3 and restore A back to baseline to complete the turn
        self.execute_stand()
        self.get_logger().info("Turn Right completed.")

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
