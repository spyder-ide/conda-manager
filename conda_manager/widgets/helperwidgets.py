# -*- coding: utf-8 -*-

"""
Helper widgets.
"""

# Standard library imports
from __future__ import absolute_import, division, print_function

# Third party imports
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QHBoxLayout, QLineEdit,  QPushButton
import qtawesome as qta


class ButtonSearch(QPushButton):
    pass


class LineEditSearch(QLineEdit):
    def __init__(self, *args, **kwargs):
        super(LineEditSearch, self).__init__(*args, **kwargs)
        self._empty = True
        self._show_icons = False
        self.button_icon = ButtonSearch()

        self.button_icon.setDefault(True)
        self.button_icon.setFocusPolicy(Qt.NoFocus)

        layout = QHBoxLayout()
        layout.addWidget(self.button_icon, 0, Qt.AlignRight)
        layout.setSpacing(0)
        layout.addSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Signals
        self.textEdited.connect(self.update_box)
        self.button_icon.clicked.connect(self.clear_text)

        self.update_box(None)
        self.set_icon_size(16, 16)
        self.setTabOrder(self, self.button_icon)

    def set_icon_size(self, width, height):
        self.button_icon.setMaximumSize(QSize(width, height))
        self.setStyleSheet('LineEditSearch '
                           '{{padding-right: {0}px;}}'.format(width))

    def set_icon_visibility(self, value):
        self._show_icons = value
        self.update_box()

    def setProperty(self, name, value):
        super(LineEditSearch, self).setProperty(name, value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def update_box(self, text=None):
        if text:
            if self._show_icons:
                self.button_icon.setIcon(qta.icon('fa.remove'))
            self.button_icon.setProperty('_remove', True)
        else:
            if self._show_icons:
                self.button_icon.setIcon(qta.icon('fa.search'))
            self.button_icon.setProperty('_remove', False)
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

    def update_style_sheet(self, style_sheet=None):
        if style_sheet is not None:
            self.button_icon.setStyleSheet(style_sheet)

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
