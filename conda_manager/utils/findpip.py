#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
"""

# Local imports
import json
import os.path as osp

# Third party imports
import pip


PIP_LIST_SCRIPT = osp.realpath(__file__).replace('.pyc', '.py')


def main():
    pip_packages = {}
    for package in pip.get_installed_distributions():
        name = package.project_name
        version = package.version
        full_name = "{0}-{1}-pip".format(name.lower(), version)
        pip_packages[full_name] = {'version': version}
    data = json.dumps(pip_packages)
    print(data)


if __name__ == '__main__':
    main()
