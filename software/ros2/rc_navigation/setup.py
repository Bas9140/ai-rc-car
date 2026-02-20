from setuptools import find_packages, setup
import os
from glob import glob

package_name = "rc_navigation"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages",
         ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "config"),
         glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Bas Venema",
    maintainer_email="basvenema1992@gmail.com",
    description="GPS waypoint navigatie voor de AI RC Car",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "navigation_node = rc_navigation.navigation_node:main",
        ],
    },
)
