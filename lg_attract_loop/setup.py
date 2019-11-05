#!/usr/bin/env python3

from distutils.core import setup
from catkin_pkg.python_setup import generate_distutils_setup

d = generate_distutils_setup(
    packages=['lg_attract_loop'],
    package_dir={'': 'src'},
    scripts=[],
    requires=[]
)

setup(**d)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
