from setuptools import find_packages, setup

package_name = "rc_avoidance"

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
    description="Obstakelvermijding voor de AI RC Car",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "avoidance_node = rc_avoidance.avoidance_node:main",
        ],
    },
)
