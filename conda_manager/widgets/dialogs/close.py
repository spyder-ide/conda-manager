# Third party imports
from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (QApplication, QDialogButtonBox, QDialog,
                            QHBoxLayout, QLabel, QPushButton, QVBoxLayout)


class ClosePackageManagerDialog(QDialog):
    """
    """
    def __init__(self, *args, **kwargs):
        super(ClosePackageManagerDialog, self).__init__(*args, **kwargs)
        self.label_icon = QLabel()
        self.label_about = QLabel('Conda is still busy.\n\n'
                                  'Do you want to cancel the process?')
        self.button_ok = QPushButton('Yes')
        self.button_cancel = QPushButton('No')
        self.buttonbox = QDialogButtonBox(Qt.Horizontal)

        # Widget setup
        self.buttonbox.addButton(self.button_ok, QDialogButtonBox.ActionRole)
        self.buttonbox.addButton(self.button_cancel,
                                 QDialogButtonBox.ActionRole)
#        self.label_icon.setPixmap(QPixmap(images.ANACONDA_ICON_64_PATH))
        self.setWindowTitle("Cancel Process")

        # Layouts
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.label_icon, 0, Qt.AlignTop)
        h_layout.addSpacing(10)
        h_layout.addWidget(self.label_about)

        main_layout = QVBoxLayout()
        main_layout.addLayout(h_layout)
        main_layout.addSpacing(20)
        main_layout.addWidget(self.buttonbox)
        self.setLayout(main_layout)

        # Signals
        self.button_ok.clicked.connect(self.accept)
        self.button_cancel.clicked.connect(self.reject)


def test():
    app = QApplication([])
    dlg = ClosePackageManagerDialog(parent=None)
    reply = dlg.exec_()
    print(reply)


if __name__ == '__main__':
    test()
