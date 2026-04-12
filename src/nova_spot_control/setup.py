from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'nova_spot_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROS2 Developer',
    maintainer_email='developer@todo.todo',
    description='Control package for Nova Mini Spot using Voice commands and PCA9685',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'voice_command_node = nova_spot_control.voice_command_node:main',
            'robot_control_node = nova_spot_control.robot_control_node:main'
        ],
    },
)
