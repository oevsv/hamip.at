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
    # The modules live in the "hamip.at/" directory rather than an importable
    # package (the directory name contains a dot), so they are exposed as
    # top-level modules.
    package_dir={"": "hamip.at"},
    py_modules=[
        "update",
        "hamnetdb_util",
        "powerdns_util",
        "pubip_util",
        "get_dns_zone_util",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests",
        "PyYAML",
        "dnspython>=2.0",
    ],
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Topic :: Internet :: Name Service (DNS)",
    ],
)
