# -*- coding:utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License
# -----------------------------------------------------------------------------
"""Bottstrap script."""

# Standard library imports
import os.path as osp
import sys

# Get current dir
print("Executing from source checkout")
DEVPATH = osp.dirname(osp.abspath(__file__))

# Patch sys.path
sys.path.insert(0, DEVPATH)
print("01. Added {0} to sys.path".format(DEVPATH))

# Run the app
from conda_manager.app import main
main()
