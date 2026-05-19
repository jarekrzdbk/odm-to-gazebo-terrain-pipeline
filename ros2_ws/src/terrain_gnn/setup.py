from setuptools import setup
package_name = "terrain_gnn"
setup(
    name=package_name, version="0.0.1", packages=[package_name],
    data_files=[("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
                (f"share/{package_name}", ["package.xml"])],
    install_requires=["setuptools"], zip_safe=True, maintainer="Your Name", maintainer_email="you@example.com",
    description="GNN traversability scaffold", license="MIT",
    entry_points={"console_scripts": ["train_gnn = terrain_gnn.train_gnn:main"]})
