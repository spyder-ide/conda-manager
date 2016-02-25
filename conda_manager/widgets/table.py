# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""
"""

from __future__ import (division, print_function, unicode_literals,
                        with_statement)

# Standard library imports
import os
import gettext

# Third party imports
from qtpy.QtCore import Qt, QPoint, QSize, QUrl, Signal
from qtpy.QtGui import QDesktopServices, QIcon, QPalette
from qtpy.QtWidgets import (QAbstractItemView, QItemDelegate, QMenu,
                            QTableView)

# Local imports
from conda_manager.models.filter import MultiColumnSortFilterProxy
from conda_manager.models.packages import CondaPackagesModel
from conda_manager.utils import get_image_path
from conda_manager.utils import constants as const
from conda_manager.utils.py3compat import to_text_string
from conda_manager.utils.qthelpers import add_actions, create_action

_ = gettext.gettext
HIDE_COLUMNS = [const.COL_STATUS, const.COL_URL, const.COL_LICENSE,
                const.COL_REMOVE, const.COL_ACTION_VERSION]


class CustomDelegate(QItemDelegate):
    def sizeHint(self, style, model_index):
        column = model_index.column()
        if column in [const.COL_PACKAGE_TYPE] + const.ACTION_COLUMNS:
            return QSize(24, 24)
        else:
            return QItemDelegate.sizeHint(self, style, model_index)


class CondaPackagesTable(QTableView):
    """ """
    WIDTH_TYPE = 24
    WIDTH_NAME = 120
    WIDTH_ACTIONS = 24
    WIDTH_VERSION = 70

    sig_status_updated = Signal(str, bool, list, bool)
    sig_conda_action_requested = Signal(str, int, str, object, object)
    sig_pip_action_requested = Signal(str, int)
    sig_actions_updated = Signal(int)

    def __init__(self, parent):
        super(CondaPackagesTable, self).__init__(parent)
        self._parent = parent
        self._searchbox = u''
        self._filterbox = const.ALL
        self._delegate = CustomDelegate(self)
        self.row_count = None
        self._advanced_mode = True

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

#        self.setSelectionBehavior(QAbstractItemView.SelectRows)
#        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().hide()
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setItemDelegate(self._delegate)
        self.setShowGrid(False)
        self.setWordWrap(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._palette = QPalette()

        # Header setup
        self._hheader = self.horizontalHeader()
        # TODO: Change this to use a qtpy constant once a new version
        # of qtpy is released
        if os.environ['QT_API'] == 'pyqt5':
            self._hheader.setSectionResizeMode(self._hheader.Fixed)
        else:
            self._hheader.setResizeMode(self._hheader.Fixed)
        self._hheader.setStyleSheet("""QHeaderView {border: 0px;
                                                    border-radius: 0px;};
                                                    """)
        self.setPalette(self._palette)
        self.sortByColumn(const.COL_NAME, Qt.AscendingOrder)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.hide_columns()

    def setup_model(self, packages, data, metadata_links={}):
        """ """
        self.proxy_model = MultiColumnSortFilterProxy(self)
        self.source_model = CondaPackagesModel(self, packages, data)
        self.proxy_model.setSourceModel(self.source_model)
        self.setModel(self.proxy_model)
        self.metadata_links = metadata_links

        # FIXME: packages sizes... move to a better place?
        packages_sizes = {}
        for name in packages:
            packages_sizes[name] = packages[name].get('size')
        self._packages_sizes = packages_sizes

        # Custom Proxy Model setup
        self.proxy_model.setDynamicSortFilter(True)

        filter_text = \
            (lambda row, text, status: (
             all([t in row[const.COL_NAME].lower() for t in
                 to_text_string(text).lower().split()]) or
             all([t in row[const.COL_DESCRIPTION].lower() for t in
                 to_text_string(text).split()])))

        filter_status = (lambda row, text, status:
                         to_text_string(row[const.COL_STATUS]) in
                         to_text_string(status))
        self.model().add_filter_function('status-search', filter_status)
        self.model().add_filter_function('text-search', filter_text)

        # Signals and slots
        self.verticalScrollBar().valueChanged.connect(self.resize_rows)

        self.hide_columns()
        self.resize_rows()
        self.refresh_actions()
#        self.resizeRowsToContents()

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

        hide = HIDE_COLUMNS
        if self._advanced_mode:
            columns = const.ACTION_COLUMNS[:]
            columns.remove(const.COL_ACTION)
            hide += columns
        else:
            hide += [const.COL_ACTION]

        for col in hide:
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
                             to_text_string(const.MIXGRADABLE)])
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
        else:
            group = to_text_string(group)

        if self.proxy_model is not None:
            self.proxy_model.set_filter(text, group)
            self.resize_rows()

        # Update label count
        count = self.verticalHeader().count()
        if count == 0:
            count_text = _("0 packages available ")
        elif count == 1:
            count_text = _("1 package available ")
        elif count > 1:
            count_text = to_text_string(count) + _(" packages available ")

        if text != '':
            count_text = count_text + _('matching "{0}"').format(text)

        self.sig_status_updated.emit(count_text, False, [0, 0], True)

    def search_string_changed(self, text):
        """ """
        text = to_text_string(text)
        self._searchbox = text
        self.filter_changed()

    def filter_status_changed(self, text):
        """ """
        if text not in const.PACKAGE_STATUS:
            text = const.PACKAGE_STATUS[text]

        for key in const.COMBOBOX_VALUES:
            val = const.COMBOBOX_VALUES[key]
            if to_text_string(val) == to_text_string(text):
                group = val
                break
        self._filterbox = group
        self.filter_changed()

    def resizeEvent(self, event):
        """Override Qt method"""
        w = self.width()
        width_start = 20

        if self._advanced_mode:
            action_cols = [const.ACTION_COLUMNS[-1], 0]
        else:
            action_cols = const.ACTION_COLUMNS[:-1]

        self.setColumnWidth(const.COL_START, width_start)
        self.setColumnWidth(const.COL_PACKAGE_TYPE, self.WIDTH_TYPE)
        self.setColumnWidth(const.COL_NAME, self.WIDTH_NAME)
        self.setColumnWidth(const.COL_VERSION, self.WIDTH_VERSION)
        w_new = w - (width_start + self.WIDTH_TYPE + self.WIDTH_NAME +
                     self.WIDTH_VERSION +
                     (len(action_cols) + 1)*self.WIDTH_ACTIONS)
        self.setColumnWidth(const.COL_DESCRIPTION, w_new)

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

            if (column == const.COL_INSTALL and
                    model.is_installable(model_index)):
                model.update_row_icon(model_index.row(), const.COL_INSTALL)

            elif (column == const.COL_INSTALL and
                    model.is_removable(model_index)):
                model.update_row_icon(model_index.row(), const.COL_REMOVE)

            elif ((column == const.COL_UPGRADE and
                   model.is_upgradable(model_index)) or
                  (column == const.COL_DOWNGRADE and
                   model.is_downgradable(model_index))):
                model.update_row_icon(model_index.row(), model_index.column())

            else:
                self._model_index_clicked = None
                self.valid = False

    def action_released(self):
        """ """
        model = self.source_model
        model_index = self._model_index_clicked

        actions = {const.COL_INSTALL: const.ACTION_INSTALL,
                   const.COL_REMOVE: const.ACTION_REMOVE,
                   const.COL_UPGRADE: const.ACTION_UPGRADE,
                   const.COL_DOWNGRADE: const.ACTION_DOWNGRADE,
                   }

        if model_index:
            column = model_index.column()

            if column == const.COL_INSTALL and model.is_removable(model_index):
                column = const.COL_REMOVE
            self.source_model.update_row_icon(model_index.row(), column)

            if self.valid:
                row_data = self.source_model.row(model_index.row())
                type_ = row_data[const.COL_PACKAGE_TYPE]
                name = row_data[const.COL_NAME]
                version = self.source_model.get_package_version(name)
                versions = self.source_model.get_package_versions(name)

                if not versions:
                    versions = [version]

                action = actions.get(column, None)

                if type_ == const.CONDA_PACKAGE:
                    self.sig_conda_action_requested.emit(name, action, version,
                                                         versions,
                                                         self._packages_sizes)
                elif type_ == const.PIP_PACKAGE:
                    self.sig_pip_action_requested.emit(name, action)
                else:
                    pass

    def set_advanced_mode(self, value=True):
        self._advanced_mode = value
#        self.resizeEvent(None)

    def set_action_status(self, model_index, status=const.ACTION_NONE,
                          version=None):
        self.source_model.set_action_status(model_index, status, version)
        self.refresh_actions()

    def context_menu_requested(self, event):
        """
        Custom context menu.
        """
        if self.proxy_model is None:
            return

        index = self.current_index
        model_index = self.proxy_model.mapToSource(index)
        row = self.source_model.row(model_index.row())
        column = model_index.column()

        if column == const.COL_ACTION:
            is_installable = self.source_model.is_installable(model_index)
            is_removable = self.source_model.is_removable(model_index)
            is_upgradable = self.source_model.is_upgradable(model_index)

            action_status = self.source_model.action_status(model_index)
            actions = []
            action_unmark = create_action(
                self,
                _('Unmark'),
                triggered=lambda: self.set_action_status(model_index,
                                                         const.ACTION_NONE))
            action_install = create_action(
                self,
                _('Mark for installation'),
                triggered=lambda: self.set_action_status(model_index,
                                                         const.ACTION_INSTALL))
            action_upgrade = create_action(
                self,
                _('Mark for upgrade'),
                triggered=lambda: self.set_action_status(model_index,
                                                         const.ACTION_UPGRADE))
            action_remove = create_action(
                self,
                _('Mark for removal'),
                triggered=lambda: self.set_action_status(model_index,
                                                         const.ACTION_REMOVE))

            name = self.source_model.row(model_index.row())[const.COL_NAME]
            versions = self.source_model.get_package_versions(name)
            version_actions = []
            for version in reversed(versions):
                if version != self.source_model.get_package_version(name):
                    def trigger(model_index=model_index,
                                action=const.ACTION_INSTALL,
                                version=versions):
                        return lambda: self.set_action_status(model_index,
                                                              action,
                                                              version)
                    version_action = create_action(
                        self,
                        version,
                        icon=QIcon(),
                        triggered=trigger(model_index, const.ACTION_INSTALL,
                                          version))
                    version_actions.append(version_action)

            install_versions_menu = QMenu('Mark for specific version '
                                          'installation', self)
            add_actions(install_versions_menu, version_actions)
            actions = [action_unmark, action_install, action_upgrade,
                       action_remove]
            if len(version_actions) > 1:
                actions += [None, install_versions_menu]

            if action_status is const.ACTION_NONE:
                action_unmark.setDisabled(True)
                action_install.setDisabled(not is_installable)
                action_upgrade.setDisabled(not is_upgradable)
                action_remove.setDisabled(not is_removable)
                install_versions_menu.setDisabled(False)
            else:
                action_unmark.setDisabled(False)
                action_install.setDisabled(True)
                action_upgrade.setDisabled(True)
                action_remove.setDisabled(True)
                install_versions_menu.setDisabled(True)

        elif column in [const.COL_VERSION]:
            name = self.source_model.row(model_index.row())[const.COL_NAME]
            versions = self.source_model.get_package_versions(name)
            actions = []
            for version in reversed(versions):
                actions.append(create_action(self, version,
                                             icon=QIcon()))
        else:
            name, license_ = row[const.COL_NAME], row[const.COL_LICENSE]

            metadata = self.metadata_links.get(name, {})
            pypi = metadata.get('pypi', '')
            home = metadata.get('home', '')
            dev = metadata.get('dev', '')
            docs = metadata.get('docs', '')

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
        if len(actions) > 1:
            self._menu = QMenu(self)
            pos = QPoint(event.x(), event.y())
            add_actions(self._menu, actions)
            self._menu.popup(self.viewport().mapToGlobal(pos))

    def get_actions(self):
        return self.source_model.get_actions()

    def clear_actions(self):
        self.source_model.clear_actions()
        self.refresh_actions()

    def refresh_actions(self):
        actions_per_package_type = self.source_model.get_actions()
        number_of_actions = 0
        for type_ in actions_per_package_type:
            actions = actions_per_package_type[type_]
            for key in actions:
                data = actions[key]
                number_of_actions += len(data)
        self.sig_actions_updated.emit(number_of_actions)

    def open_url(self, url):
        """
        Open link from action in default operating system  browser.
        """
        if url is None:
            return
        QDesktopServices.openUrl(QUrl(url))
