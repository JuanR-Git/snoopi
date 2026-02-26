from setuptools import find_packages, setup

setup(
    name='snoopi_mock',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    install_requires=['setuptools'],
    entry_points={
        'console_scripts': [
            'mock_robot_publisher = snoopi_mock.mock_robot_publisher:main',
        ],
    },
)
