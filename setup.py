from os import path

from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt") as f:
    requirements = [l for l in f.read().splitlines() if l]


setup(
    name="moni1000f",
    version="0.0.1",
    description="A tool for handling the Moni1000 Forest data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Tetsuo I. Kohyama (Moni1000 Network Center)",
    author_email="tetsuo_kohyama@ees.hokudai.ac.jp",
    license="MIT",
    url="https://github.com/kohyamat/moni1000f",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={"console_scripts": ["moni1000utils = moni1000f.datacheck_gui:main"]},
)
