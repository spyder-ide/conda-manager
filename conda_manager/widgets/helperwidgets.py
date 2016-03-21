# -*- coding: utf-8 -*-

"""
Helper widgets.
"""

# Standard library imports
from __future__ import absolute_import, division, print_function

# Third party imports
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QLineEdit,  QPushButton
import qtawesome as qta


class ButtonSearch(QPushButton):
    pass


class LineEditSearch(QLineEdit):
    def __init__(self, *args, **kwargs):
        super(LineEditSearch, self).__init__(*args, **kwargs)
        self._empty = True
        self.button_icon = ButtonSearch()

        self.button_icon.setDefault(True)
        self.button_icon.setFocusPolicy(Qt.NoFocus)

        layout = QHBoxLayout()
        layout.addWidget(self.button_icon, 0, Qt.AlignRight)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Signals
        self.textEdited.connect(self.update_box)
        self.button_icon.clicked.connect(self.clear_text)

        self.update_box(None)
        self.setTabOrder(self, self.button_icon)

    def update_box(self, text=None):
        if text:
            self.button_icon.setIcon(qta.icon('fa.remove'))
        else:
            self.button_icon.setIcon(qta.icon('fa.search'))
        self._empty = not bool(text)
        self.button_icon.setDisabled(self._empty)

#        right = self.button_icon.width()
#        top = self.contentsMargins().top()
#        left = self.contentsMargins().left()
#        bottom = self.contentsMargins().bottom()
#        self.setContentsMargins(left, top, right, bottom)

    def clear_text(self):
        self.setText('')
        self.setFocus()
        self.update_box()

    def keyPressEvent(self, event):
        """
        Qt override.
        """
        key = event.key()
        if key in [Qt.Key_Escape]:
            self.clear_text()
        else:
            super(LineEditSearch, self).keyPressEvent(event)


def test():
    from conda_manager.utils.qthelpers import qapplication
    app = qapplication()

    w = LineEditSearch()
    w.show()
    app.exec_()


if __name__ == '__main__':
    test()
