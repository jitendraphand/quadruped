import rclpy
from rclpy.node import Node
import board
import busio
from adafruit_pca9685 import PCA9685
import json
import os
import sys

CALIBRATION_FILE = os.path.expanduser('~/.nova_spot_calibration.json')

class MotorCalibrationNode(Node):
    def __init__(self):
        super().__init__('motor_calibration_node')

        # Initialize I2C and PCA9685
        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.pca = PCA9685(self.i2c)
            self.pca.frequency = 50
            self.get_logger().info("Hardware initialized successfully.")
        except Exception as e:
            self.get_logger().error(f"Failed to initialize hardware: {e}")
            sys.exit(1)

        # Default resting pulse values for perfectly aligned position (135 deg for A/B, 90 deg for C)
        # Using 1500us as the mechanical center pulse.
        self.calibrated_pulses = {str(c): 1500 for c in [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]}
        self.load_calibration()

    def load_calibration(self):
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, 'r') as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        if k in self.calibrated_pulses:
                            self.calibrated_pulses[k] = v
                self.get_logger().info(f"Loaded calibration from {CALIBRATION_FILE}")
            except Exception as e:
                self.get_logger().error(f"Failed to load calibration: {e}")
        else:
            self.get_logger().info("No existing calibration found. Using defaults.")

    def save_calibration(self):
        try:
            with open(CALIBRATION_FILE, 'w') as f:
                json.dump(self.calibrated_pulses, f, indent=4)
            self.get_logger().info(f"Calibration saved to {CALIBRATION_FILE}")
        except Exception as e:
            self.get_logger().error(f"Failed to save calibration: {e}")

    def pulse_to_duty(self, pulse_us):
        # 50Hz = 20,000 us period.
        # The adafruit_pca9685 library expects a 16-bit duty cycle (0-65535),
        # even though the hardware is 12-bit.
        duty = int((pulse_us * 65535) / 20000)
        return duty

    def set_pulse(self, channel, pulse_us):
        if 0 <= channel <= 15:
            duty = self.pulse_to_duty(pulse_us)
            self.pca.channels[channel].duty_cycle = duty

    def interactive_loop(self):
        print("\n--- Nova Mini Spot Motor Calibration ---")
        print("Channels:")
        print("  Front Left:  A(0),  B(1),  C(2)")
        print("  Front Right: A(4),  B(5),  C(6)")
        print("  Back Left:   A(8),  B(9),  C(10)")
        print("  Back Right:  A(12), B(13), C(14)")
        print("Type 'q' to quit and save, or 'l' to list current pulses.")

        while True:
            try:
                chan_input = input("\nEnter channel to calibrate (or q/l): ").strip().lower()
                if chan_input == 'q':
                    self.save_calibration()
                    print("Exiting...")
                    break
                if chan_input == 'l':
                    for c in [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14]:
                        print(f"Channel {c}: {self.calibrated_pulses[str(c)]} us")
                    continue

                channel = int(chan_input)
                if str(channel) not in self.calibrated_pulses:
                    print("Invalid channel for this robot. Valid channels: 0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14")
                    continue

                print(f"Calibrating Channel {channel}. Current pulse: {self.calibrated_pulses[str(channel)]} us")
                self.set_pulse(channel, self.calibrated_pulses[str(channel)])

                while True:
                    pulse_input = input(f"[Ch {channel}] Enter new pulse (us) or '+' to add 10, '-' to sub 10, 'b' to back: ").strip().lower()
                    if pulse_input == 'b':
                        break

                    current_pulse = self.calibrated_pulses[str(channel)]
                    if pulse_input == '+':
                        new_pulse = current_pulse + 10
                    elif pulse_input == '-':
                        new_pulse = current_pulse - 10
                    else:
                        try:
                            new_pulse = int(pulse_input)
                        except ValueError:
                            print("Invalid input.")
                            continue

                    # Safe range roughly 500-2500 us
                    new_pulse = max(500, min(2500, new_pulse))
                    self.calibrated_pulses[str(channel)] = new_pulse
                    self.set_pulse(channel, new_pulse)
                    print(f"Channel {channel} set to {new_pulse} us")

            except KeyboardInterrupt:
                self.save_calibration()
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = MotorCalibrationNode()

    # Run the interactive loop
    node.interactive_loop()

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

if __name__ == '__main__':
    main()
