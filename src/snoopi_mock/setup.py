import os
from glob import glob

from setuptools import find_packages, setup

setup(
    name='snoopi_mock',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/snoopi_mock']),
        ('share/snoopi_mock', ['package.xml']),
    ],
    install_requires=['setuptools'],
    entry_points={
        'console_scripts': [
            'mock_robot_publisher = snoopi_mock.mock_robot_publisher:main',
        ],
    },
)
