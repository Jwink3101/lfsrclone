#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Read the version from the file itself. This is a bit hacky but works.
# And while eval is usually unsafe, I control the code it calls so it is fine

with open("lfsrclone.py", "rt") as file:
    for line in file:
        line = line.strip()
        if line.startswith("__version__"):
            __version__ = line.split("=", 1)[1].strip()
            __version__ = eval(__version__)
            break
    else:
        raise ValueError("Could not find __version__ in source")

from setuptools import setup

setup(
    name="lfsrclone",
    py_modules=["lfsrclone"],
    long_description=open("readme.md").read(),
    entry_points={"console_scripts": ["lfsrclone=lfsrclone:Main"],},
    python_requires=">=3.6",
    version=__version__,
    description="git-lfs rclone custom transfer agent",
    url="https://github.com/Jwink3101/lfsrclone",
    author="Justin Winokur",
    author_email="Jwink3101@@users.noreply.github.com",
    license="MIT",
)
