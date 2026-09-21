from setuptools import setup

package_name = 'simple_teleop'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@email.com',
    description='Simple continuous teleop',
    license='MIT',
    entry_points={
        'console_scripts': [
            'teleop = simple_teleop.teleop_node:main',
        ],
    },
)
