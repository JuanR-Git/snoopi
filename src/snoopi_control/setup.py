from setuptools import find_packages, setup

setup(
    name='snoopi_control',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/snoopi_control']),
        ('share/snoopi_control', ['package.xml']),
    ],
    install_requires=['setuptools'],
    entry_points={
        'console_scripts': [
            'safe_space = snoopi_control.safe_space:main',
            'autonomous_walk = snoopi_control.autonomous_walk:main',
            'sample_move = snoopi_control.sample_move:main',
            'sit_stand = snoopi_control.sit_stand:main',
	    'following = snoopi_control.following:main',
            'patient_walk = snoopi_control.patient_walk:main',
            'basic_mover = snoopi_control.basic_mover:main',
        ],
    },
)
