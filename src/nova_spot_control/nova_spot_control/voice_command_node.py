import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import speech_recognition as sr
from openai import OpenAI
import os
import threading
import io
import wave
import time

# INSERT YOUR OPENAI API KEY HERE
OPENAI_API_KEY = "your-openai-api-key-here"

class VoiceCommandNode(Node):
    def __init__(self):
        super().__init__('voice_command_node')

        # Initialize OpenAI client
        # In a real scenario, it's safer to use os.environ.get("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

        # Initialize Speech Recognizer
        self.recognizer = sr.Recognizer()

        # Valid commands
        self.valid_commands = ["sit", "stand", "walk", "turn right"]

        # Publisher to send the detected command
        self.command_publisher = self.create_publisher(String, 'robot_command', 10)

        # Subscriber to receive robot status (whether it has finished executing)
        self.status_subscriber = self.create_subscription(
            Bool,
            'robot_status',
            self.status_callback,
            10
        )

        # State variable to track if the robot is busy executing a command
        self.robot_busy = False

        # Start the listening thread
        self.listen_thread = threading.Thread(target=self.audio_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()

        self.get_logger().info("Voice Command Node Initialized. Listening for commands...")

    def status_callback(self, msg):
        # When robot finishes executing, it sends True, meaning it's ready
        if msg.data:
            self.robot_busy = False
            self.get_logger().info("Robot ready. Resuming listening.")

    def audio_loop(self):
        # Use default microphone as audio source
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            self.get_logger().info("Microphone calibrated. Ready to hear.")

            while rclpy.ok():
                if self.robot_busy:
                    # If robot is executing a command, sleep briefly and wait
                    time.sleep(0.1)
                    continue

                try:
                    self.get_logger().info("Listening...")
                    # Listen for audio
                    audio = self.recognizer.listen(source, timeout=5.0, phrase_time_limit=3.0)

                    if self.robot_busy:
                        # Double check in case status changed while listening
                        continue

                    # Process audio
                    self.process_audio(audio)

                except sr.WaitTimeoutError:
                    # Timeout reached, loop again
                    pass
                except Exception as e:
                    self.get_logger().error(f"Error during recording: {e}")

    def process_audio(self, audio):
        try:
            # Save audio to a temporary WAV file for OpenAI Whisper
            # OpenAI requires a file-like object with a name
            wav_data = audio.get_wav_data()

            # Using an in-memory file for efficiency, but we must name it so openai knows the format
            audio_file = io.BytesIO(wav_data)
            audio_file.name = "audio.wav"

            self.get_logger().info("Transcribing via OpenAI...")

            # Call OpenAI Whisper API
            transcript = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

            text = transcript.text.lower()
            self.get_logger().info(f"Heard: {text}")

            # Check for commands
            for cmd in self.valid_commands:
                if cmd in text:
                    self.get_logger().info(f"Command detected: {cmd}")

                    # Pause listening by setting robot_busy
                    self.robot_busy = True

                    # Publish command
                    msg = String()
                    msg.data = cmd
                    self.command_publisher.publish(msg)
                    break

        except Exception as e:
            self.get_logger().error(f"Error during transcription: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = VoiceCommandNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

if __name__ == '__main__':
    main()
