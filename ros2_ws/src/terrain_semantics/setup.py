from setuptools import setup
package_name = "terrain_semantics"
setup(
    name=package_name, version="0.0.1", packages=[package_name],
    data_files=[("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
                (f"share/{package_name}", ["package.xml"]),
                (f"share/{package_name}/launch", ["launch/semantic_segmentation.launch.py"])],
    install_requires=["setuptools"], zip_safe=True, maintainer="Your Name", maintainer_email="you@example.com",
    description="Semantic segmentation node scaffold", license="MIT",
    entry_points={"console_scripts": ["semantic_segmentation_node = terrain_semantics.semantic_segmentation_node:main"]})
