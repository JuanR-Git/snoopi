from setuptools import find_packages, setup

setup(
    name='snoopi_system_monitor',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    install_requires=['setuptools', 'psutil'],
    entry_points={
        'console_scripts': [
            'system_monitor = snoopi_system_monitor.system_monitor:main',
        ],
    },
)
