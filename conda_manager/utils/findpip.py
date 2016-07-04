#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright © 2015- The Spyder Development Team
# Copyright © 2014-2015 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License
# -----------------------------------------------------------------------------
"""List pip pacakges in a given conda environments."""

# Standard library imports
import json
import os.path as osp

# Third party imports
import pip

PIP_LIST_SCRIPT = osp.realpath(__file__).replace('.pyc', '.py')


def main():
    """Use pip to find pip installed packages in a given prefix."""
    pip_packages = {}
    for package in pip.get_installed_distributions():
        name = package.project_name
        version = package.version
        full_name = "{0}-{1}-pip".format(name.lower(), version)
        pip_packages[full_name] = {'version': version}
    data = json.dumps(pip_packages)
    print(data)


if __name__ == '__main__':  # pragma: no cover
    try:
        main()
    except:
        # Something went wrong, so the package list is the empty list
        print('{}')

