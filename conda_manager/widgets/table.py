# -*- coding: utf-8 -*-
"""

"""

import gettext

from qtpy.QtCore import Qt, QPoint, QUrl
from qtpy.QtGui import QDesktopServices, QIcon, QPalette
from qtpy.QtWidgets import QAbstractItemView, QMenu, QTableView

from ..models.filter import MultiColumnSortFilterProxy
from ..models.packages import CondaPackagesModel
from ..utils import get_image_path
from ..utils import constants as const
from ..utils.py3compat import to_text_string
from ..utils.qthelpers import add_actions, create_action

_ = gettext.gettext
HIDE_COLUMNS = [const.STATUS, const.URL, const.LICENSE, const.REMOVE]


class CondaPackagesTable(QTableView):
    """ """
    WIDTH_NAME = 120
    WIDTH_ACTIONS = 24
    WIDTH_VERSION = 70

    def __init__(self, parent):
        super(CondaPackagesTable, self).__init__(parent)
        self._parent = parent
        self._searchbox = u''
        self._filterbox = const.ALL
        self.row_count = None

        # To manage icon states
        self._model_index_clicked = None
        self.valid = False
        self.column_ = None
        self.current_index = None

        # To prevent triggering the keyrelease after closing a dialog
        # but hititng enter on it
        self.pressed_here = False

        self.source_model = None
        self.proxy_model = None

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().hide()
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._palette = QPalette()

        # Header setup
        self._hheader = self.horizontalHeader()
        self._hheader.setResizeMode(self._hheader.Fixed)
        self._hheader.setStyleSheet("""QHeaderView {border: 0px;
                                                    border-radius: 0px;};""")
        self.setPalette(self._palette)
        self.sortByColumn(const.NAME, Qt.AscendingOrder)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def setup_model(self, packages_names, packages_versions, row_data):
        """ """
        self.proxy_model = MultiColumnSortFilterProxy(self)
        self.source_model = CondaPackagesModel(self, packages_names,
                                               packages_versions, row_data)
        self.proxy_model.setSourceModel(self.source_model)
        self.setModel(self.proxy_model)

        # Custom Proxy Model setup
        self.proxy_model.setDynamicSortFilter(True)

        filter_text = \
            (lambda row, text, status: (
             all([t in row[const.NAME].lower() for t in
                 to_text_string(text).lower().split()]) or
             all([t in row[const.DESCRIPTION].lower() for t in
                 to_text_string(text).split()])))

        filter_status = (lambda row, text, status:
                         to_text_string(row[const.STATUS]) in
                         to_text_string(status))
        self.model().add_filter_function('status-search', filter_status)
        self.model().add_filter_function('text-search', filter_text)

        # signals and slots
        self.verticalScrollBar().valueChanged.connect(self.resize_rows)

        self.hide_columns()

    def resize_rows(self):
        """ """
        delta_y = 10
        height = self.height()
        y = 0
        while y < height:
            row = self.rowAt(y)
            self.resizeRowToContents(row)
            row_height = self.rowHeight(row)
            self.setRowHeight(row, row_height + delta_y)
            y += self.rowHeight(row) + delta_y

    def hide_columns(self):
        """ """
        for col in const.COLUMNS:
            self.showColumn(col)
        for col in HIDE_COLUMNS:
            self.hideColumn(col)

    def hide_action_columns(self):
        """ """
        for col in const.COLUMNS:
            self.showColumn(col)
        for col in HIDE_COLUMNS + const.ACTION_COLUMNS:
            self.hideColumn(col)

    def filter_changed(self):
        """Trigger the filter"""
        group = self._filterbox
        text = self._searchbox

        if group in [const.ALL]:
            group = ''.join([to_text_string(const.INSTALLED),
                             to_text_string(const.UPGRADABLE),
                             to_text_string(const.NOT_INSTALLED),
                             to_text_string(const.DOWNGRADABLE),
                             to_text_string(const.MIXGRADABLE),
                             to_text_string(const.NOT_INSTALLABLE)])
        elif group in [const.INSTALLED]:
            group = ''.join([to_text_string(const.INSTALLED),
                             to_text_string(const.UPGRADABLE),
                             to_text_string(const.DOWNGRADABLE),
                             to_text_string(const.MIXGRADABLE)])
        elif group in [const.UPGRADABLE]:
            group = ''.join([to_text_string(const.UPGRADABLE),
                             to_text_string(const.MIXGRADABLE)])
        elif group in [const.DOWNGRADABLE]:
            group = ''.join([to_text_string(const.DOWNGRADABLE),
                             to_text_string(const.MIXGRADABLE)])
        elif group in [const.ALL_INSTALLABLE]:
            group = ''.join([to_text_string(const.INSTALLED),
                             to_text_string(const.UPGRADABLE),
                             to_text_string(const.NOT_INSTALLED),
                             to_text_string(const.DOWNGRADABLE),
                             to_text_string(const.MIXGRADABLE)])
        else:
            group = to_text_string(group)

        if self.proxy_model is not None:
            self.proxy_model.set_filter(text, group)
            self.resize_rows()

        # update label count
        count = self.verticalHeader().count()
        if count == 0:
            count_text = _("0 packages available ")
        elif count == 1:
            count_text = _("1 package available ")
        elif count > 1:
            count_text = to_text_string(count) + _(" packages available ")

        if text != '':
            count_text = count_text + _('matching "{0}"').format(text)

        self._parent._update_status(status=count_text, hide=False, env=True)

    def search_string_changed(self, text):
        """ """
        text = to_text_string(text)
        self._searchbox = text
        self.filter_changed()

    def filter_status_changed(self, text):
        """ """
        if hasattr(const.COMBOBOX_VALUES, 'iteritems'):
            items = const.COMBOBOX_VALUES.iteritems()
        else:
            items = const.COMBOBOX_VALUES.items()
        for key, val in items:
            if to_text_string(val) == to_text_string(text):
                group = val
                break
        self._filterbox = group
        self.filter_changed()

    def resizeEvent(self, event):
        """Override Qt method"""
        w = self.width()
        self.setColumnWidth(const.NAME, self.WIDTH_NAME)
        self.setColumnWidth(const.VERSION, self.WIDTH_VERSION)
        w_new = w - (self.WIDTH_NAME + self.WIDTH_VERSION +
                     (len(const.ACTION_COLUMNS) + 1)*self.WIDTH_ACTIONS)
        self.setColumnWidth(const.DESCRIPTION, w_new)

        for col in const.ACTION_COLUMNS:
            self.setColumnWidth(col, self.WIDTH_ACTIONS)
        QTableView.resizeEvent(self, event)
        self.resize_rows()

    def keyPressEvent(self, event):
        """Override Qt method"""
        QTableView.keyPressEvent(self, event)
        if event.key() in [Qt.Key_Enter, Qt.Key_Return]:
            index = self.currentIndex()
            self.action_pressed(index)
            self.pressed_here = True

    def keyReleaseEvent(self, event):
        """Override Qt method"""
        QTableView.keyReleaseEvent(self, event)
        if event.key() in [Qt.Key_Enter, Qt.Key_Return] and self.pressed_here:
            self.action_released()
        self.pressed_here = False

    def mousePressEvent(self, event):
        """Override Qt method"""
        QTableView.mousePressEvent(self, event)
        self.current_index = self.currentIndex()

        if event.button() == Qt.LeftButton:
            pos = QPoint(event.x(), event.y())
            index = self.indexAt(pos)
            self.action_pressed(index)
        elif event.button() == Qt.RightButton:
            self.context_menu_requested(event)

    def mouseReleaseEvent(self, event):
        """Override Qt method"""
        if event.button() == Qt.LeftButton:
            self.action_released()

    def action_pressed(self, index):
        """ """
        column = index.column()

        if self.proxy_model is not None:
            model_index = self.proxy_model.mapToSource(index)
            model = self.source_model

            self._model_index_clicked = model_index
            self.valid = True

            if column == const.INSTALL and model.is_installable(model_index):
                model.update_row_icon(model_index.row(), const.INSTALL)
            elif column == const.INSTALL and model.is_removable(model_index):
                model.update_row_icon(model_index.row(), const.REMOVE)
            elif ((column == const.UPGRADE and
                   model.is_upgradable(model_index)) or
                  (column == const.DOWNGRADE and
                   model.is_downgradable(model_index))):
                model.update_row_icon(model_index.row(), model_index.column())
            else:
                self._model_index_clicked = None
                self.valid = False

    def action_released(self):
        """ """
        model = self.source_model
        model_index = self._model_index_clicked

        if model_index:
            column = model_index.column()

            if column == const.INSTALL and model.is_removable(model_index):
                column = const.REMOVE
            self.source_model.update_row_icon(model_index.row(), column)

            if self.valid:
                name = self.source_model.row(model_index.row())[const.NAME]
                versions = self.source_model.get_package_versions(name)
                version = self.source_model.get_package_version(name)

                self._parent._run_action(name, column, version, versions)

    def context_menu_requested(self, event):
        """ Custom context menu"""
        index = self.current_index
        model_index = self.proxy_model.mapToSource(index)
        row = self.source_model.row(model_index.row())

        name, license_ = row[const.NAME], row[const.LICENSE]
        pos = QPoint(event.x(), event.y())
        self._menu = QMenu(self)

        metadata = self._parent.get_package_metadata(name)
        pypi = metadata['pypi']
        home = metadata['home']
        dev = metadata['dev']
        docs = metadata['docs']

        q_pypi = QIcon(get_image_path('python.png'))
        q_home = QIcon(get_image_path('home.png'))
        q_docs = QIcon(get_image_path('conda_docs.png'))

        if 'git' in dev:
            q_dev = QIcon(get_image_path('conda_github.png'))
        elif 'bitbucket' in dev:
            q_dev = QIcon(get_image_path('conda_bitbucket.png'))
        else:
            q_dev = QIcon()

        if 'mit' in license_.lower():
            lic = 'http://opensource.org/licenses/MIT'
        elif 'bsd' == license_.lower():
            lic = 'http://opensource.org/licenses/BSD-3-Clause'
        else:
            lic = None

        actions = []

        if license_ != '':
            actions.append(create_action(self, _('License: ' + license_),
                                         icon=QIcon(), triggered=lambda:
                                         self.open_url(lic)))
            actions.append(None)

        if pypi != '':
            actions.append(create_action(self, _('Python Package Index'),
                                         icon=q_pypi, triggered=lambda:
                                         self.open_url(pypi)))
        if home != '':
            actions.append(create_action(self, _('Homepage'),
                                         icon=q_home, triggered=lambda:
                                         self.open_url(home)))
        if docs != '':
            actions.append(create_action(self, _('Documentation'),
                                         icon=q_docs, triggered=lambda:
                                         self.open_url(docs)))
        if dev != '':
            actions.append(create_action(self, _('Development'),
                                         icon=q_dev, triggered=lambda:
                                         self.open_url(dev)))
        if len(actions):
            add_actions(self._menu, actions)
            self._menu.popup(self.viewport().mapToGlobal(pos))

    def open_url(self, url):
        """Open link from action in default operating system  browser"""
        if url is None:
            return
        QDesktopServices.openUrl(QUrl(url))
