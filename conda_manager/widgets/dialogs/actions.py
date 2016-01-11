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
import gettext

# Third party imports
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                            QDialogButtonBox, QGridLayout, QLabel, QSpacerItem,
                            QTableView, QWidget)

# Local imports
from conda_manager.models.dependencies import CondaDependenciesModel
from conda_manager.utils import conda_api_q, sort_versions
from conda_manager.utils import constants as const
from conda_manager.utils.py3compat import to_text_string


_ = gettext.gettext


class CondaPackageActionDialog(QDialog):
    """ """
    def __init__(self, parent, prefix, name, action, version, versions):
        super(CondaPackageActionDialog, self).__init__(parent)
        self._parent = parent
        self._prefix = prefix
        self._version_text = None
        self._name = name
        self._dependencies_dic = {}
        self._conda_process = conda_api_q.CondaProcess(self)

        # Widgets
        self.label = QLabel(self)
        self.combobox_version = QComboBox()
        self.label_version = QLabel(self)
        self.widget_version = None
        self.table_dependencies = None

        self.checkbox = QCheckBox(_('Install dependencies (recommended)'))
        self.bbox = QDialogButtonBox(QDialogButtonBox.Ok |
                                     QDialogButtonBox.Cancel, Qt.Horizontal,
                                     self)

        self.button_ok = self.bbox.button(QDialogButtonBox.Ok)
        self.button_cancel = self.bbox.button(QDialogButtonBox.Cancel)

        self.button_cancel.setDefault(True)
        self.button_cancel.setAutoDefault(True)

        dialog_size = QSize(300, 90)

        # Helper variable values
        action_title = {const.UPGRADE: _("Upgrade package"),
                        const.DOWNGRADE: _("Downgrade package"),
                        const.REMOVE: _("Remove package"),
                        const.INSTALL: _("Install package")}

        # Versions might have duplicates from different builds
        versions = sort_versions(list(set(versions)), reverse=True)

        # FIXME: There is a bug, a package installed by anaconda has version
        # astropy 0.4 and the linked list 0.4 but the available versions
        # in the json file do not include 0.4 but 0.4rc1... so...
        # temporal fix is to check if inside list otherwise show full list
        if action == const.UPGRADE:
            if version in versions:
                index = versions.index(version)
                versions = versions[:index]
            else:
                versions = versions
        elif action == const.DOWNGRADE:
            if version in versions:
                index = versions.index(version)
                versions = versions[index+1:]
            else:
                versions = versions
        elif action == const.REMOVE:
            versions = [version]
            self.combobox_version.setEnabled(False)

        if len(versions) == 1:
            if action == const.REMOVE:
                labeltext = _('Package version to remove:')
            else:
                labeltext = _('Package version available:')
            self.label_version.setText(versions[0])
            self.widget_version = self.label_version
        else:
            labeltext = _("Select package version:")
            self.combobox_version.addItems(versions)
            self.widget_version = self.combobox_version

        self.label.setText(labeltext)
        self.label_version.setAlignment(Qt.AlignLeft)
        self.table_dependencies = QWidget(self)

        self._layout = QGridLayout()
        self._layout.addWidget(self.label, 0, 0, Qt.AlignVCenter |
                               Qt.AlignLeft)
        self._layout.addWidget(self.widget_version, 0, 1, Qt.AlignVCenter |
                               Qt.AlignRight)

        self.widgets = [self.checkbox, self.button_ok, self.widget_version,
                        self.table_dependencies]
        row_index = 1

        # Create a Table
        if action in [const.INSTALL, const.UPGRADE, const.DOWNGRADE]:
            table = QTableView(self)
            dialog_size = QSize(dialog_size.width() + 40, 300)
            self.table_dependencies = table
            row_index = 1
            self._layout.addItem(QSpacerItem(10, 5), row_index, 0)
            self._layout.addWidget(self.checkbox, row_index + 1, 0, 1, 2)
            self.checkbox.setChecked(True)
            self._changed_version(versions[0])

            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.verticalHeader().hide()
            table.horizontalHeader().hide()
            table.setAlternatingRowColors(True)
            table.setShowGrid(False)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.horizontalHeader().setStretchLastSection(True)

        self._layout.addWidget(self.table_dependencies, row_index + 2, 0, 1, 2,
                               Qt.AlignHCenter)
        self._layout.addItem(QSpacerItem(10, 5), row_index + 3, 0)
        self._layout.addWidget(self.bbox, row_index + 6, 0, 1, 2,
                               Qt.AlignHCenter)

        title = "{0}: {1}".format(action_title[action], name)
        self.setLayout(self._layout)
        self.setMinimumSize(dialog_size)
        self.setFixedSize(dialog_size)
        self.setWindowTitle(title)
        self.setModal(True)

        # Signals and slots
        self.bbox.accepted.connect(self.accept)
        self.bbox.rejected.connect(self.close)
        self.combobox_version.currentIndexChanged.connect(
            self._changed_version)
        self.checkbox.stateChanged.connect(self._changed_checkbox)
        self._conda_process.sig_finished.connect(self._on_process_finished)

    def _changed_version(self, version, dependencies=True):
        """ """
        self._set_gui_disabled(True)
        install_dependencies = (self.checkbox.checkState() == 2)
        self._version_text = to_text_string(version)
        self._get_dependencies(install_dependencies)

    def _get_dependencies(self, dependencies=True):
        """ """
        package_name = [self._name + '=' + self._version_text]

        # Temporal fix
        self._conda_process.dependencies(prefix=self._prefix,
                                         pkgs=package_name,
                                         dep=dependencies)

    def _changed_checkbox(self, state):
        """ """
        if state:
            self._changed_version(self._version_text)
        else:
            self._changed_version(self._version_text, dependencies=False)

    def _on_process_finished(self, boo):
        """ """
        if self.isVisible():
            dic = self._conda_process.output
            self.dependencies_dic = dic
            self._set_dependencies_table()
            self._set_gui_disabled(False)

    def _set_dependencies_table(self):
        """ """
        table = self.table_dependencies
        dic = self.dependencies_dic
        table.setModel(CondaDependenciesModel(self, dic))
        table.resizeColumnsToContents()
        table.resizeColumnToContents(1)

    def _set_gui_disabled(self, value):
        """ """
        if value:
            table = self.table_dependencies
            table.setModel(CondaDependenciesModel(self, {}))
            table.resizeColumnsToContents()
            table.setDisabled(True)
        else:
            table = self.table_dependencies
            table.setDisabled(False)

        for widget in self.widgets:
            widget.setDisabled(value)
