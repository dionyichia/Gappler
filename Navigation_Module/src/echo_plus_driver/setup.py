from setuptools import setup

package_name = 'echo_plus_driver'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='iot22',
    maintainer_email='iot22@todo.todo',
    description='Echo Plus CAN driver (ROS2)',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'echo_plus_node = echo_plus_driver.echo_plus_node:main',
        ],
    },
)
