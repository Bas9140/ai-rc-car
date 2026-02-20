from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'rc_bringup'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Bas Venema',
    maintainer_email='basvenema1992@gmail.com',
    description='Launch files and config for AI RC Car',
    license='MIT',
    entry_points={'console_scripts': []},
)
