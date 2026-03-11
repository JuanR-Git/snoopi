from setuptools import find_packages, setup

setup(
    name='snoopi_command_bridge',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/snoopi_command_bridge']),
        ('share/snoopi_command_bridge', ['package.xml']),
    ],
    install_requires=['setuptools'],
    entry_points={
        'console_scripts': [
            'command_bridge = snoopi_command_bridge.command_bridge:main',
        ],
    },
)
