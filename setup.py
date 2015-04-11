#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Setup script for conda-manager
"""

from setuptools import setup, find_packages


def read_version():
    with open("conda_manager/__init__.py") as f:
        lines = f.read().splitlines()
        for l in lines:
            if "__version__" in l:
                return l.split("=")[1].strip().replace("'", '').replace('"', '')


def readme():
    return str(open('README.rst').read())


setup(
    name='conda-manager',
    version=read_version(),
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    keywords=["Qt PyQt4 PyQt5 PySide conda conda-api binstar"],
    url='https://github.com/spyder-ide/conda-manager',
    license='MIT',
    author='Gonzalo Peña-Castellanos',
    author_email='goanpeca@gmail.com',
    maintainer='Gonzalo Peña-Castellanos',
    maintainer_email='goanpeca@gmail.com',
    description='A stand alone PyQt/PySide GUI application for managing conda '
                'packages and environments.',
    long_description=readme(),
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

