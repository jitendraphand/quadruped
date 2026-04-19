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

            # Track current offsets to allow smooth interpolation
            self.current_offsets = {c: 0 for c in [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]}

            self.get_logger().info("Hardware initialized successfully.")
        except Exception as e:
            self.get_logger().error(f"Failed to initialize hardware: {e}")
            self.hardware_initialized = False
            self.current_offsets = {c: 0 for c in [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]}

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
        elif command == "wave":
            self.execute_wave()
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
        elif channel in [2, 6, 10, 14]:  # Motor C: 1000 - 2000 us
            return max(1000, min(2000, pulse_us))
        return pulse_us

    def set_servos(self, offset_dict):
        """
        Set multiple servos at once using a dictionary of {channel: pulse_offset}.
        Offsets are added to the calibrated base pulse, then clamped to safe ranges.
        """
        for channel, offset in offset_dict.items():
            self.current_offsets[channel] = offset

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

    def set_servos_smooth(self, target_offsets, duration=0.5, steps=20):
        """
        Smoothly interpolate servos from current offsets to target_offsets over duration.
        """
        if not target_offsets:
            return

        start_offsets = {ch: self.current_offsets.get(ch, 0) for ch in target_offsets.keys()}
        sleep_time = duration / steps

        for step in range(1, steps + 1):
            fraction = step / steps
            interp_offsets = {}
            for ch in target_offsets.keys():
                interp_offsets[ch] = start_offsets[ch] + (target_offsets[ch] - start_offsets[ch]) * fraction
            self.set_servos(interp_offsets)
            time.sleep(sleep_time)

    def execute_sit(self):
        if self.current_state == "sit":
            self.get_logger().info("Already sitting.")
            time.sleep(1) # buffer time
            return

        self.get_logger().info("Executing Sit...")

        # Sitting offsets: bend all legs backward at the knee
        # Motor A: 0 offset
        # Motor B: +450 us
        # Motor C: +500 us (bending backward at the knee)
        sit_offsets = {
            # Front Left
            0: 0, 1: 450, 2: 500,
            # Front Right
            4: 0, 5: 450, 6: 500,
            # Back Left
            8: 0, 9: 450, 10: 500,
            # Back Right
            12: 0, 13: 450, 14: 500
        }
        self.set_servos_smooth(sit_offsets, duration=1.0)

        self.current_state = "sit"
        self.get_logger().info("Sit completed.")

    def execute_stand(self):
        if self.current_state == "stand":
            self.get_logger().info("Already standing.")
            time.sleep(1) # buffer time
            return

        self.get_logger().info("Executing Stand...")

        # Standing pose with slight backward bending at the knee (Motor C)
        # Motor A: 0, Motor B: 0, Motor C: +150
        stand_offsets = {
            0: 0, 1: 0, 2: 150,
            4: 0, 5: 0, 6: 150,
            8: 0, 9: 0, 10: 150,
            12: 0, 13: 0, 14: 150
        }
        self.set_servos_smooth(stand_offsets, duration=1.0)

        self.current_state = "stand"
        self.get_logger().info("Stand completed.")

    def execute_walk(self):
        if self.current_state != "stand":
            self.get_logger().info("Must stand first to walk. Standing up...")
            self.execute_stand()
            time.sleep(1)

        self.get_logger().info("Executing Walk (10 steps)...")

        # Lower body while walking by adding constant +250 us offset to knee (Motor C)
        # B offsets reduced from +/- 200 to +/- 100 for smaller steps
        knee_base = 250
        lift_offset = -150  # relative to knee_base, so C goes to 100 to lift slightly

        # Transition smoothly to the lower walk-ready stance before starting the loop
        self.set_servos_smooth({
            0: 0, 1: 0, 2: knee_base,
            4: 0, 5: 0, 6: knee_base,
            8: 0, 9: 0, 10: knee_base,
            12: 0, 13: 0, 14: knee_base
        }, duration=0.5)

        for step in range(10):
            self.get_logger().info(f"Step {step+1}/10")

            # Lift legs 1 (Front Left) and 4 (Back Right)
            self.set_servos_smooth({
                0: 0, 1: 0, 2: knee_base + lift_offset,
                4: 0, 5: 0, 6: knee_base,
                8: 0, 9: 0, 10: knee_base,
                12: 0, 13: 0, 14: knee_base + lift_offset
            }, duration=0.15)

            # Move 1 & 4 forward (Motor B +/- 100 for small steps)
            self.set_servos_smooth({
                0: 0, 1: 100, 2: knee_base,
                4: 0, 5: 0, 6: knee_base,
                8: 0, 9: 0, 10: knee_base,
                12: 0, 13: -100, 14: knee_base
            }, duration=0.15)

            # Lift legs 2 (Front Right) and 3 (Back Left)
            self.set_servos_smooth({
                0: 0, 1: 0, 2: knee_base,
                4: 0, 5: 0, 6: knee_base + lift_offset,
                8: 0, 9: 0, 10: knee_base + lift_offset,
                12: 0, 13: 0, 14: knee_base
            }, duration=0.15)

            # Move 2 & 3 forward
            self.set_servos_smooth({
                0: 0, 1: 0, 2: knee_base,
                4: 0, 5: 100, 6: knee_base,
                8: 0, 9: -100, 10: knee_base,
                12: 0, 13: 0, 14: knee_base
            }, duration=0.15)

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
        self.set_servos_smooth({
            # Lift (C: -300 relative to baseline) and rotate (A: +/- 300)
            0: 300, 1: 0, 2: -150,   # FL (lift is C -300 from +150 stand offset -> -150)
            4: 0, 5: 0, 6: 150,      # FR (stay at stand)
            8: 0, 9: 0, 10: 150,     # BL (stay at stand)
            12: -300, 13: 0, 14: -150 # BR
        }, duration=0.3)

        # Step 2: Put down pair 1 & 4
        self.set_servos_smooth({
            0: 300, 1: 0, 2: 150,
            4: 0, 5: 0, 6: 150,
            8: 0, 9: 0, 10: 150,
            12: -300, 13: 0, 14: 150
        }, duration=0.3)

        # Step 3: Lift diagonal pair 2 (FR) & 3 (BL) and rotate A to match, while restoring A for 1 & 4
        self.set_servos_smooth({
            0: 0, 1: 0, 2: 150,         # FL restored
            4: -300, 5: 0, 6: -150,     # FR lifted and rotated
            8: 300, 9: 0, 10: -150,     # BL lifted and rotated
            12: 0, 13: 0, 14: 150       # BR restored
        }, duration=0.3)

        # Step 4: Put down pair 2 & 3 and restore A back to baseline to complete the turn
        self.execute_stand()
        self.get_logger().info("Turn Right completed.")

    def execute_wave(self):
        if self.current_state != "stand":
            self.get_logger().info("Must stand first to wave. Standing up...")
            self.execute_stand()
            time.sleep(1)

        self.get_logger().info("Executing Wave...")

        # Lift forward right leg (Motor C on FR is channel 6, Motor B is 5, Motor A is 4)
        # FR mapping: A(4), B(5), C(6)

        # Lift the leg and move it forward slightly
        self.set_servos_smooth({
            4: 0, 5: 200, 6: -300
        }, duration=0.5)

        # Wave a few times (move inward and outward using Motor A)
        for _ in range(3):
            # Move outward
            self.set_servos_smooth({
                4: 300, 5: 200, 6: -300
            }, duration=0.3)
            # Move inward
            self.set_servos_smooth({
                4: -300, 5: 200, 6: -300
            }, duration=0.3)

        # Move back to center lift position
        self.set_servos_smooth({
            4: 0, 5: 200, 6: -300
        }, duration=0.3)

        # Return to stand
        self.execute_stand()
        self.get_logger().info("Wave completed.")


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
