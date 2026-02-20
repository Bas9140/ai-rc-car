from setuptools import find_packages, setup

package_name = 'rc_sensors'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Bas Venema',
    maintainer_email='basvenema1992@gmail.com',
    description='GPS, IMU and ultrasonic sensor nodes for AI RC Car',
    license='MIT',
    entry_points={
        'console_scripts': [
            'gps_node        = rc_sensors.gps_node:main',
            'ultrasonic_node = rc_sensors.ultrasonic_node:main',
            'imu_node        = rc_sensors.imu_node:main',
        ],
    },
)
