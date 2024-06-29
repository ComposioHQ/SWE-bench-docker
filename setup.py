"""
Setup configuration for swe-bench-docker
"""

from pathlib import Path

from setuptools import find_packages, setup


setup(
    name="swe_bench_docker",
    version="0.0.1",
    author="aorwall",
    author_email="",
    description="Dockerization of run_evaluation.py",
    long_description=(Path(__file__).parent / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    url="https://github.com/aorwall/SWE-bench-docker",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires="==3.11",
    packages=find_packages(include=["swe_bench_docker/*"]),
    install_requires=[
            "swebench==1.1.0",
        ],
    include_package_data=True,
)
