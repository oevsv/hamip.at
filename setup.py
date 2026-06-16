import os

from setuptools import setup

_here = os.path.abspath(os.path.dirname(__file__))


def _read(filename):
    path = os.path.join(_here, filename)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    return ""


setup(
    name="hamip-at",
    version="0.1.0",
    description="Build and maintain the hamip.at DNS zone from HamnetDB",
    long_description=_read("README.md"),
    long_description_content_type="text/markdown",
    author="Dietmar Zlabinger (OE3DZW)",
    url="https://github.com/oevsv/hamip.at",
    license="Apache-2.0",
    packages=["hamipat"],
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "requests",
        "PyYAML",
        "dnspython>=2.0",
    ],
    entry_points={
        "console_scripts": [
            "hamip-update=hamipat.cli:main",
        ],
    },
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Topic :: Internet :: Name Service (DNS)",
    ],
)
