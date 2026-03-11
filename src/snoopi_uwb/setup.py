from setuptools import find_packages, setup

setup(
    name='snoopi_uwb',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/snoopi_uwb']),
        ('share/snoopi_uwb', ['package.xml']),
    ],
    install_requires=['setuptools', 'pyserial'],
    entry_points={
        'console_scripts': [
            'uwb_reader = snoopi_uwb.uwb_reader:main',
        ],
    },
)
