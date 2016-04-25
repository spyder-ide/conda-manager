# -*- coding: utf-8 -*-

import os.path as osp
import sys

# Get current dir
print("Executing from source checkout")
DEVPATH = osp.dirname(osp.abspath(__file__))

# Patch sys.path
sys.path.insert(0, DEVPATH)
print("01. Added %s to sys.path" % DEVPATH)

# Run the app
from conda_manager.app import main
main()
