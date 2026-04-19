import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import time
import board
import busio
from adafruit_pca9685 import PCA9685
import json
import os

CALIBRATION_FILE = os.path.expanduser('~/.nova_spot_calibration.json')

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

            # Load calibrations or fallback to 1500us
            self.calibrated_pulses = {str(c): 1500 for c in [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]}
            self.load_calibration()
            self.hardware_initialized = True

            self.get_logger().info("Hardware initialized successfully.")
        except Exception as e:
            self.get_logger().error(f"Failed to initialize hardware: {e}")
            self.hardware_initialized = False

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

    def load_calibration(self):
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, 'r') as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        if k in self.calibrated_pulses:
                            self.calibrated_pulses[k] = v
                self.get_logger().info(f"Loaded calibrated pulses from {CALIBRATION_FILE}")
            except Exception as e:
                self.get_logger().error(f"Failed to load calibration: {e}")
        else:
            self.get_logger().info("No calibration file found. Using default 1500us for all.")

    def publish_ready_status(self):
        msg = Bool()
        msg.data = True
        self.status_publisher.publish(msg)
        self.get_logger().info("Finished executing. Ready for next command.")

    def pulse_to_duty(self, pulse_us):
        # 50Hz = 20,000 us period.
        # The adafruit_pca9685 library expects a 16-bit duty cycle (0-65535).
        return int((pulse_us * 65535) / 20000)

    def clamp_pulse(self, channel, pulse_us):
        """Clamp pulse based on motor allowed physical ranges."""
        if channel in [0, 4, 8, 12]:  # Motor A: 1000 - 2000 us (roughly +/- 67.5 deg from center)
            return max(1000, min(2000, pulse_us))
        elif channel in [1, 5, 9, 13]:  # Motor B: 1000 - 2000 us
            return max(1000, min(2000, pulse_us))
        elif channel in [2, 6, 10, 14]:  # Motor C: 1100 - 1900 us (roughly +/- 60 deg from center)
            return max(1100, min(1900, pulse_us))
        return pulse_us

    def set_servos(self, offset_dict):
        """
        Set multiple servos at once using a dictionary of {channel: pulse_offset}.
        Offsets are added to the calibrated base pulse, then clamped to safe ranges.
        """
        if not self.hardware_initialized:
            self.get_logger().warn("Hardware not initialized, simulating servo movement.")
            return

        for channel, offset in offset_dict.items():
            str_chan = str(channel)
            if str_chan in self.calibrated_pulses:
                base_pulse = self.calibrated_pulses[str_chan]
                target_pulse = base_pulse + offset
                safe_pulse = self.clamp_pulse(channel, target_pulse)
                duty = self.pulse_to_duty(safe_pulse)
                self.pca.channels[channel].duty_cycle = duty

    def execute_sit(self):
        if self.current_state == "sit":
            self.get_logger().info("Already sitting.")
            time.sleep(1) # buffer time
            return

        self.get_logger().info("Executing Sit...")

        # Sitting offsets based on calibrated baselines.
        # Motor A: 0 offset
        # Motor B: +450 us
        # Motor C: -600 us
        sit_offsets = {
            # Front Left
            0: 0, 1: 450, 2: -600,
            # Front Right
            4: 0, 5: 450, 6: -600,
            # Back Left
            8: 0, 9: 450, 10: -600,
            # Back Right
            12: 0, 13: 450, 14: -600
        }
        self.set_servos(sit_offsets)

        time.sleep(2) # Give it time to physically move
        self.current_state = "sit"
        self.get_logger().info("Sit completed.")

    def execute_stand(self):
        if self.current_state == "stand":
            self.get_logger().info("Already standing.")
            time.sleep(1) # buffer time
            return

        self.get_logger().info("Executing Stand...")

        # Aligned baseline for standing. Since calibrated pulse IS the baseline, offsets are 0.
        stand_offsets = {c: 0 for c in [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]}
        self.set_servos(stand_offsets)

        time.sleep(2) # Give it time to physically move
        self.current_state = "stand"
        self.get_logger().info("Stand completed.")

    def execute_walk(self):
        if self.current_state != "stand":
            self.get_logger().info("Must stand first to walk. Standing up...")
            self.execute_stand()
            time.sleep(1)

        self.get_logger().info("Executing Walk (10 steps)...")

        # Basic placeholder gait using pulse offsets
        for step in range(10):
            self.get_logger().info(f"Step {step+1}/10")

            # Lift legs 1 (Front Left) and 4 (Back Right)
            # Lift = Motor C (knee) offset -300us
            self.set_servos({
                0: 0, 1: 0, 2: -300,
                4: 0, 5: 0, 6: 0,
                8: 0, 9: 0, 10: 0,
                12: 0, 13: 0, 14: -300
            })
            time.sleep(0.2)

            # Move 1 & 4 forward (Motor B adjusted)
            # Motor B +200us on one, -200us on the other (opposite sides)
            self.set_servos({
                0: 0, 1: 200, 2: 0,
                4: 0, 5: 0, 6: 0,
                8: 0, 9: 0, 10: 0,
                12: 0, 13: -200, 14: 0
            })
            time.sleep(0.2)

            # Lift legs 2 (Front Right) and 3 (Back Left)
            self.set_servos({
                0: 0, 1: 0, 2: 0,
                4: 0, 5: 0, 6: -300,
                8: 0, 9: 0, 10: -300,
                12: 0, 13: 0, 14: 0
            })
            time.sleep(0.2)

            # Move 2 & 3 forward
            self.set_servos({
                0: 0, 1: 0, 2: 0,
                4: 0, 5: 200, 6: 0,
                8: 0, 9: -200, 10: 0,
                12: 0, 13: 0, 14: 0
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

        # Step 1: Lift diagonal pair 1 (FL) & 4 (BR) and rotate A using offsets
        self.set_servos({
            # Lift (C: -300) and rotate (A: +/- 300)
            0: 300, 1: 0, 2: -300,   # FL
            4: 0, 5: 0, 6: 0,        # FR
            8: 0, 9: 0, 10: 0,       # BL
            12: -300, 13: 0, 14: -300 # BR
        })
        time.sleep(0.3)

        # Step 2: Put down pair 1 & 4
        self.set_servos({
            0: 300, 1: 0, 2: 0,
            4: 0, 5: 0, 6: 0,
            8: 0, 9: 0, 10: 0,
            12: -300, 13: 0, 14: 0
        })
        time.sleep(0.3)

        # Step 3: Lift diagonal pair 2 (FR) & 3 (BL) and rotate A to match, while restoring A for 1 & 4
        self.set_servos({
            0: 0, 1: 0, 2: 0,         # FL restored
            4: -300, 5: 0, 6: -300,   # FR lifted and rotated
            8: 300, 9: 0, 10: -300,   # BL lifted and rotated
            12: 0, 13: 0, 14: 0       # BR restored
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
