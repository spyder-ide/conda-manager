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
                        with_statement)
import gettext
import sys

# Third party imports
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (QDialog, QHBoxLayout, QFrame, QListWidget,
                            QListWidgetItem, QVBoxLayout)

# Local imports
from conda_manager.api import ManagerAPI
from conda_manager.widgets import (ButtonPackageChannelAdd,
                                   ButtonPackageChannelRemove,
                                   ButtonPackageChannelUpdate)
import qtawesome as qta

_ = gettext.gettext


class ListWidgetChannels(QListWidget):
    pass


class ListWidgetItemChannels(QListWidgetItem):
    pass


class DialogChannels(QDialog):
    """
    A dialog to add delete and select active channels to search for packages.
    """
    sig_channels_updated = Signal(object, object)  # channels, active_channels

    def __init__(self, parent=None, channels=None, active_channels=None,
                 conda_url=None, flat=True):

        # Check arguments: active channels, must be within channels
        for channel in active_channels:
            if channel not in channels:
                raise Exception("'active_channels' must be also within "
                                "'channels'")

        super(DialogChannels, self).__init__(parent)
        self._parent = parent
        self._channels = channels
        self._active_channels = active_channels
        self._conda_url = conda_url
        self._edited_channel_text = ''
        self._temp_channels = channels
        self.api = ManagerAPI()

        # Widgets
        self.list = ListWidgetChannels(self)
        self.button_add = ButtonPackageChannelAdd('Add')
        self.button_delete = ButtonPackageChannelRemove('Remove')
        self.button_ok = ButtonPackageChannelUpdate(_('Update channels'))

        # Widget setup
#        self.button_add.setIcon(qta.icon('fa.plus'))
#        self.button_delete.setIcon(qta.icon('fa.minus'))
        self.setMinimumWidth(350)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.96)
        self.setModal(False)

        # Layout
        layout = QVBoxLayout()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.button_add)
        button_layout.addWidget(self.button_delete)

        ok_layout = QHBoxLayout()
        ok_layout.addStretch()
        ok_layout.addWidget(self.button_ok)

        layout.addLayout(button_layout)
        layout.addWidget(self.list)
        layout.addLayout(ok_layout)
        self.setLayout(layout)

        # Signals
        self.button_add.clicked.connect(self.add_channel)
        self.button_delete.clicked.connect(self.delete_channel)
        self.button_ok.clicked.connect(self.update_channels)

        self.setup()

        self.list.itemChanged.connect(self.edit_channel)
        self.button_add.setFocus()

        if flat:
            self.list.setFrameStyle(QFrame.NoFrame)
            self.list.setFrameShape(QFrame.NoFrame)

    def _height(self):
        """
        Get the height for the row in the widget based on OS font metrics.
        """
        return self.fontMetrics().height()*2

    def _url_validated(self, worker, valid, error):
        item = worker.item
        channel = item.data(Qt.DisplayRole).strip().lower()
        channel = worker.url

        if valid:
            temp = list(self._temp_channels)
            temp.append(channel)
            self._temp_channels = tuple(temp)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled |
                          Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.DisplayRole, channel)
            item.setData(Qt.DecorationRole, QIcon())
        else:
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled |
                          Qt.ItemIsSelectable | Qt.ItemIsEditable)
            item.setData(Qt.DisplayRole, channel)
            item.setCheckState(Qt.Unchecked)
            item.setIcon(qta.icon('fa.warning'))
            item.setToolTip("The channel seems to be invalid.")
            self.list.editItem(item)

        self.list.itemChanged.connect(self.edit_channel)
        self.button_add.setDisabled(False)
        self.button_delete.setDisabled(False)

    def keyPressEvent(self, event):
        """
        Qt override.
        """
        key = event.key()
        if key in [Qt.Key_Return, Qt.Key_Enter]:
            self.update_channels()
        elif key in [Qt.Key_Escape]:
            self.reject()

    # --- Public API
    # -------------------------------------------------------------------------
    def update_style_sheet(self, style_sheet=None):
        if style_sheet:
            self.setStyleSheet(style_sheet)
            self.style_sheet = style_sheet

    def setup(self):
        for channel in sorted(self._channels):
            item = ListWidgetItemChannels(channel, self.list)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            if channel in self._active_channels:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

            self.list.addItem(item)
            item.setSizeHint(QSize(item.sizeHint().width(), self._height()))

        self.list.setCurrentRow(0)
        self.refresh()
        self.set_tab_order()

    def set_tab_order(self):
        self.setTabOrder(self.button_add, self.button_delete)
        self.setTabOrder(self.button_delete, self.list)
        self.setTabOrder(self.list, self.button_ok)

    def add_channel(self):
        item = ListWidgetItemChannels('', self.list)
        item.setFlags(item.flags() | Qt.ItemIsEditable |
                      Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        self.list.addItem(item)
        item.setSizeHint(QSize(item.sizeHint().width(), self._height()))
        self.list.setCurrentRow(self.list.count()-1)
        self.list.editItem(item)
        self.refresh()

    def edit_channel(self, item):
        channel = item.data(Qt.DisplayRole).strip().lower()

        if channel in self._temp_channels:
            return

        if channel != u'':
            self._edited_channel_text = channel

            if channel.startswith('https://') or channel.startswith('http://'):
                url = channel
            else:
                url = "{0}/{1}".format(self._conda_url, channel)

            if url[-1] == '/':
                url = url[:-1]
            plat = self.api.conda_platform()
            repodata_url = "{0}/{1}/{2}".format(url, plat, 'repodata.json')

            worker = self.api.download_is_valid_url(repodata_url)
            worker.sig_finished.connect(self._url_validated)
            worker.item = item
            worker.url = url
            worker.repodata_url = repodata_url

            self.list.itemChanged.disconnect()
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            self.button_add.setDisabled(True)
            self.button_delete.setDisabled(True)

    def delete_channel(self):
        """
        """
        index = self.list.currentIndex().row()

        if self.list.count() > 1:
            self.list.takeItem(index)
            self.button_delete.setDisabled(False)

        if self.list.count() == 1:
            self.button_delete.setDisabled(True)

    def update_channels(self):
        """
        """
        temp_active_channels = []
        channels = []

        for i in range(self.list.count()):
            item = self.list.item(i)
            channel = item.data(Qt.DisplayRole)

            if channel:
                channels.append(channel)

                if item.checkState() == Qt.Checked:
                    temp_active_channels.append(item.data(Qt.DisplayRole))

        if (sorted(channels) != sorted(self._channels) or
                sorted(temp_active_channels) != sorted(self._active_channels)):
            self.sig_channels_updated.emit(tuple(channels),
                                           tuple(temp_active_channels))
            self.accept()
        else:
            self.reject()

    def refresh(self):
        """
        Updated enabled/disabled status based on teh amount of items.
        """
        if self.list.count() == 1:
            self.button_delete.setDisabled(True)
        else:
            self.button_delete.setDisabled(False)


def test_widget():
    from spyderlib.utils.qthelpers import qapplication
    app = qapplication()
    widget = DialogChannels(
        None,
        ['http://repo.continuum.io/free', 'https://conda.anaconda.org/malev'],
        ['https://conda.anaconda.org/malev'],
        'https://conda.anaconda.org',
        )
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    test_widget()
