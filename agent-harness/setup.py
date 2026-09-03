from setuptools import find_namespace_packages, setup

setup(
    name="cli-anything-tubular-reform",
    version="1.0.0",
    description="CLI-Anything harness for tubular-reform (agent-native table reflow).",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    package_data={
        "cli_anything.tubular_reform": ["skills/*.md"],
    },
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "tubular-reform>=0.2.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-tubular-reform=cli_anything.tubular_reform.tubular_reform_cli:main",
        ],
    },
    python_requires=">=3.10",
)
