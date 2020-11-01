import codecs
import os.path

from setuptools import find_packages, setup


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="MoniSenForest",
    version=get_version("MoniSenForest/__init__.py"),
    description="Tool for handling forest plot data of the Monitoring Sites 1000 Project",
    long_description=long_description,
    url="https://github.com/MoniSenNC/MoniSenForest",
    author="Tetsuo I. Kohyama",
    author_email="tetsuo.kohyama@gmail.com",
    license="MIT",
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
    keywords="ecosystem-monitoring tree-inventory litterfall",
    packages=find_packages(),
    install_requires=["dataclasses;python_version=='3.6'", "numpy>=1.18.1", "openpyxl"],
    python_requires=">=3.6",
    package_data={
        "MoniSenForest": [
            "suppl_data/*.json",
            "suppl_data/*.md",
            "icons/*.png",
            "icons/*.svg",
        ],
    },
    entry_points={"console_scripts": ["monisenforest = MoniSenForest.app:main"]},
)
