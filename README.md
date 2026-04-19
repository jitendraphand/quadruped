# Nova Mini Spot Control Workspace

This is a ROS 2 Jazzy workspace to control a Nova Mini Spot quadruped robot using voice commands on a Raspberry Pi 4B running Ubuntu 24.04.

## Hardware Requirements
- Raspberry Pi 4B
- Nova Mini Spot (Quadruped robot, 12 servos in total)
- PCA9685 16-Channel 12-bit PWM/Servo Driver
- USB Microphone (wireless receiver plugged into Raspberry Pi USB port)
- Power supply for Raspberry Pi (5V 3A)
- Independent Power supply for Servos (e.g., 5V or 6V battery pack connected directly to PCA9685 terminal block)

## Wiring Instructions
### PCA9685 to Raspberry Pi (I2C)
- PCA9685 `VCC` -> RPi `3.3V` (Pin 1 or 17)
- PCA9685 `GND` -> RPi `GND` (Pin 6 or 9)
- PCA9685 `SDA` -> RPi `SDA` (GPIO 2, Pin 3)
- PCA9685 `SCL` -> RPi `SCL` (GPIO 3, Pin 5)

### PCA9685 Power
- Connect your servo power supply directly to the PCA9685 `V+` and `GND` screw terminals. **Do NOT power the servos directly from the Raspberry Pi** as this will cause brownouts.

### Servos to PCA9685
Connect the 12 servos to the PCA9685 board based on the motor types.

Each leg has three motors:
- **Motor A (Hip Abduction & Adduction):** Moves leg sideways. Rotation angle 270 deg (pulse 500-2500 µs). Perfectly aligned at 135 deg. Hardware clamped range: 1000-2000 µs.
- **Motor B (Hip Flexion/Extension):** Moves leg forward/back. Rotation angle 270 deg (pulse 500-2500 µs). Perfectly aligned at 135 deg. Hardware clamped range: 1000-2000 µs.
- **Motor C (Knee Bending):** Rotation angle 180 deg (pulse 900-2100 µs). Perfectly aligned at 90 deg. Hardware clamped range: 1000-2000 µs.

**PCA9685 Channel Mapping:**
- **Front Left Leg:** Motor A (0), Motor B (1), Motor C (2)
- **Front Right Leg:** Motor A (4), Motor B (5), Motor C (6)
- **Back/Rear Left Leg:** Motor A (8), Motor B (9), Motor C (10)
- **Back/Rear Right Leg:** Motor A (12), Motor B (13), Motor C (14)

*Note: Make sure the yellow/white signal wire faces the inner row (PWM), red faces the middle (V+), and brown/black faces the outer row (GND).*

### USB Microphone
- Plug the USB receiver into any available USB port on the Raspberry Pi.

## Software Setup Instructions

### 1. OS and ROS 2
Ensure your Raspberry Pi is running Ubuntu 24.04 and that you have installed **ROS 2 Jazzy Jalisco**.
Follow the official ROS 2 Jazzy installation guide for Ubuntu.

### 2. Install System Dependencies
Install necessary system packages for audio and I2C:
```bash
sudo apt update
sudo apt install python3-pyaudio portaudio19-dev python3-pip i2c-tools
```

### 3. Enable I2C on Raspberry Pi
Enable the I2C interface:
```bash
sudo raspi-config
```
Navigate to `Interface Options` -> `I2C` -> Select `Yes`. Reboot if necessary.
Verify I2C is working and detects the PCA9685 (default address is usually 0x40):
```bash
i2cdetect -y 1
```

### 4. Clone and Build the Workspace
Clone this repository to your Raspberry Pi:
```bash
mkdir -p ~/nova_spot_ws/src
cd ~/nova_spot_ws/src
git clone <your_repo_url_here> .
cd ~/nova_spot_ws
```

Install Python dependencies:
```bash
pip install -r src/requirements.txt
```
*Note: Depending on your Python environment setup in Ubuntu 24.04, you may need to use `pip install --break-system-packages` or create a virtual environment.*

### 5. Add OpenAI API Key
Open the `voice_command_node.py` file and insert your OpenAI API key:
```bash
nano src/nova_spot_control/nova_spot_control/voice_command_node.py
# Replace "your-openai-api-key-here" with your actual key
```

### 6. Build the Workspace
```bash
colcon build --packages-select nova_spot_control
source install/setup.bash
```

### 7. Motor Calibration (Highly Recommended)
Before executing walking or sitting motions, you should calibrate the "resting" pulse value for each of the 12 motors to ensure precise alignment.
The default expected resting pulse for perfect alignment (A: 135°, B: 135°, C: 90°) is 1500µs. Since mechanical linkages and servo splines vary, use the calibration node to fine-tune this resting state.

Run the calibration node (make sure the robot control node is NOT running):
```bash
ros2 run nova_spot_control motor_calibration_node
```

**Calibration Instructions:**
1. Type a channel number (e.g., `0` for Front Left Motor A) and hit Enter.
2. The servo will move to its currently stored calibration pulse (default 1500µs).
3. Type `+` to increase the pulse by 10µs, or `-` to decrease it, or enter an exact microsecond value (e.g., `1530`) to find the perfect mechanical alignment. Type `b` to go back to channel selection.
4. Once all motors are physically aligned (A and B at exactly 135°, C at exactly 90°), type `q` to quit.
5. This saves your custom resting pulses to `~/.nova_spot_calibration.json`.

*Note: The `robot_control_node` automatically loads these calibrated values on startup. All subsequent movements (sit, walk, turn) are executed as relative pulse offsets from this highly precise calibrated baseline.*

## Running the Code

Execute the launch file to start both the voice recognition and robot control nodes:
```bash
ros2 launch nova_spot_control nova_spot_launch.py
```

### Usage
Once launched, the microphone will continuously listen. Speak one of the following commands clearly:
- **"Sit"**: The robot bends all legs backward at the knee to lower itself.
- **"Stand"**: The robot returns to a standing position with a slight bend at the knees.
- **"Walk"**: The robot walks 10 steps forward using a pulse-offset gait, lowering its body slightly for stability (requires standing first).
- **"Turn right"**: The robot rotates 90 degrees about the vertical axis (requires standing first).
- **"Wave"**: The robot lifts its front right leg and waves it inward and outward (requires standing first).

All motor movements use a smooth interpolation algorithm to ensure fluid motions and prevent sudden jerks or jitters.

While a command is executing, the microphone goes inactive to prevent self-interruption. Once the movement completes and after a short buffer time, the robot will resume listening for new commands.
