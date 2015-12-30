"""
Application entry point
"""
# Standard library imports
import sys

# Third party imports
from qtpy.QtWidgets import QApplication

# Local imports
from conda_manager.app import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec_()


if __name__ == '__main__':
    main()
