from setuptools import setup
package_name = "terrain_perception"
setup(
    name=package_name, version="0.0.1", packages=[package_name],
    data_files=[("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
                (f"share/{package_name}", ["package.xml"]),
                (f"share/{package_name}/launch", ["launch/object_detector_tracker.launch.py"])],
    install_requires=["setuptools"], zip_safe=True, maintainer="Your Name", maintainer_email="you@example.com",
    description="Object detector + tracker scaffold", license="MIT",
    entry_points={"console_scripts": ["object_detector_tracker = terrain_perception.object_detector_tracker:main"]})
