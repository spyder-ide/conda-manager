# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""
Application entry point.
"""

# Standard library imports
import os
import sys

# Local imports
from conda_manager.utils.qthelpers import qapplication
from conda_manager.widgets.main_window import MainWindow


# Set Windows taskbar icon
if os.name == 'nt':
    try:
        from ctypes import windll
        windll.shell32.SetCurrentProcessExplicitAppUserModelID("conda-manager")
    except AttributeError:
        pass


def main():
    app = qapplication(sys.argv, test_time=45)
    window = MainWindow()
    window.show()
    app.exec_()


if __name__ == '__main__':
    main()
