from setuptools import find_packages, setup

package_name = "rc_perception"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages",
         ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Bas Venema",
    maintainer_email="basvenema1992@gmail.com",
    description="OAK-D Lite + YOLO perceptie voor de AI RC Car",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "oak_node       = rc_perception.oak_node:main",
            "tracking_node  = rc_perception.tracking_node:main",
            "depth_node     = rc_perception.depth_node:main",
        ],
    },
)
