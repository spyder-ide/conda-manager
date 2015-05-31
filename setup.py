#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Setup script for conda-manager
"""

from setuptools import setup, find_packages
import os
import sys


# Check for Python 3
PY3 = sys.version_info[0] == 3


def get_version():
    """ """
    with open("conda_manager/__init__.py") as f:
        lines = f.read().splitlines()
        for l in lines:
            if "__version__" in l:
                version = l.split("=")[1].strip()
                version = version.replace("'", '').replace('"', '')
                return version


def get_readme():
    """ """
    with open('README.rst') as f:
        readme = str(f.read())
    return readme


# TODO:
def get_data_files():
    """Return data_files in a platform dependent manner"""
    if sys.platform.startswith('linux'):
        if PY3:
            data_files = [('share/applications',
                           ['scripts/conda-manager3.desktop']),
                          ('share/pixmaps',
                           ['img_src/conda-manager3.png'])]
        else:
            data_files = [('share/applications',
                           ['scripts/conda-manager.desktop']),
                          ('share/pixmaps',
                           ['img_src/conda-manager.png'])]
    elif os.name == 'nt':
        data_files = [('scripts', ['img_src/conda-manager.ico'])]
    else:
        data_files = []
    return data_files


# Requirements
requirements = ['qtpy', 'qtawesome', 'requests']


setup(
    name='conda-manager',
    namespace_packages=['spyderplugins'],
    version=get_version(),
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    keywords=["Qt PyQt4 PyQt5 PySide conda conda-api binstar"],
    install_requires=requirements,
    url='https://github.com/spyder-ide/conda-manager',
    license='MIT',
    author='Gonzalo Peña-Castellanos',
    author_email='goanpeca@gmail.com',
    maintainer='Gonzalo Peña-Castellanos',
    maintainer_email='goanpeca@gmail.com',
    description='A stand alone PyQt/PySide GUI application for managing conda '
                'packages and environments.',
    long_description=get_readme(),
    entry_points={
        'gui_scripts': [
            'conda-manager = conda_manager.app.main:main'
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: X11 Applications :: Qt',
        'Environment :: Win32 (MS Windows)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Widget Sets'])
