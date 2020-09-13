from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="MoniSenForest",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["dataclasses;python_version=='3.6'", "numpy>=1.18.1", "openpyxl"],
    python_requires=">=3.6",
    package_data={
        "MoniSenForest": ["suppl_data/*.json"]
    },
    author="Tetsuo I. Kohyama",
    author_email="tetsuo.kohyama@gmail.com",
    description="Tool for handling MoniSen Forest data",
    keywords="ecosystem-monitoring tree-inventory litterfall",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Education",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    entry_points={
        "gui_scripts": [
            "monisenforest = MoniSenForest.app:main",
        ]
    },
)
