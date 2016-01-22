# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""

"""

# Standard library imports
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)
import sys

# Third party imports
from qtpy.QtCore import Qt, QSize
from qtpy.QtGui import QIcon, QPixmap
from qtpy.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit,
                            QToolButton)

# Local imports
from conda_manager.utils import get_image_path


class SearchLineEdit(QLineEdit):
    """Line edit search widget with icon and remove all button"""
    def __init__(self, parent=None, icon=True):
        super(SearchLineEdit, self).__init__(parent)
        self.setTextMargins(1, 0, 20, 0)

        if icon:
            self.setTextMargins(18, 0, 20, 0)
            self._label = QLabel(self)
            self._pixmap_icon = QPixmap(get_image_path('conda_search.png'))
            self._label.setPixmap(self._pixmap_icon)
            self._label.setStyleSheet('''border: 0px; padding-bottom: 0px;
                                      padding-left: 2px;''')

        self._pixmap = QPixmap(get_image_path('conda_del.png'))
        self.button_clear = QToolButton(self)
        self.button_clear.setIcon(QIcon(self._pixmap))
        self.button_clear.setIconSize(QSize(18, 18))
        self.button_clear.setCursor(Qt.ArrowCursor)
        self.button_clear.setStyleSheet("""QToolButton
            {background: transparent;
            padding-right: 2px; border: none; margin:0px; }""")
        self.button_clear.setVisible(False)

        # Layout
        self._layout = QHBoxLayout(self)
        self._layout.addWidget(self.button_clear, 0, Qt.AlignRight)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 2, 2, 0)

        # Signals and slots
        self.button_clear.clicked.connect(self.clear_text)
        self.textChanged.connect(self._toggle_visibility)
        self.textEdited.connect(self._toggle_visibility)

    def _toggle_visibility(self):
        """ """
        if len(self.text()) == 0:
            self.button_clear.setVisible(False)
        else:
            self.button_clear.setVisible(True)

    def sizeHint(self):
        return QSize(200, self._pixmap_icon.height())

    # Public api
    # ----------
    def clear_text(self):
        """ """
        self.setText('')
        self.setFocus()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = SearchLineEdit()
    w.show()
    sys.exit(app.exec_())
