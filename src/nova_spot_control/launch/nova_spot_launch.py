from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='nova_spot_control',
            executable='voice_command_node',
            name='voice_command_node',
            output='screen'
        ),
        Node(
            package='nova_spot_control',
            executable='robot_control_node',
            name='robot_control_node',
            output='screen'
        )
    ])
