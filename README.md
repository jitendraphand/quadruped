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
- **Motor A (Hip Abduction & Adduction):** Moves leg sideways. Rotation angle 270 deg (pulse 500-2500 µs). Perfectly aligned at 135 deg (allowed range +/- 67.5 deg).
- **Motor B (Hip Flexion/Extension):** Moves leg forward/back. Rotation angle 270 deg (pulse 500-2500 µs). Perfectly aligned at 135 deg (allowed range +/- 67.5 deg).
- **Motor C (Knee Bending):** Rotation angle 180 deg (pulse 900-2100 µs). Perfectly aligned at 90 deg (allowed range +/- 60 deg).

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

## Running the Code

Execute the launch file to start both the voice recognition and robot control nodes:
```bash
ros2 launch nova_spot_control nova_spot_launch.py
```

### Usage
Once launched, the microphone will continuously listen. Speak one of the following commands clearly:
- **"Sit"**: The robot adjusts its base joints from the baseline alignment to sit down.
- **"Stand"**: The robot assumes its perfectly aligned baseline position: Motor A at 135°, Motor B at 135°, and Motor C at 90°.
- **"Walk"**: The robot will walk 10 steps forward using a basic gait built around the aligned baseline (requires standing first).
- **"Turn right"**: The robot rotates 90 degrees about the vertical axis (requires standing first).

While a command is executing, the microphone goes inactive to prevent self-interruption. Once the movement completes and after a short buffer time, the robot will resume listening for new commands.
