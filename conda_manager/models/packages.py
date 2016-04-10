# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""
"""

# Standard library imports
import gettext

# Third party imports
from qtpy.compat import to_qvariant
from qtpy.QtCore import (QAbstractTableModel, QModelIndex, QSize, Qt)
from qtpy.QtGui import QPalette, QColor

# Local imports
from conda_manager.utils import get_icon, sort_versions
from conda_manager.utils import constants as C


_ = gettext.gettext


class CondaPackagesModel(QAbstractTableModel):
    """
    Abstract Model to handle the packages in a conda environment.
    """
    def __init__(self, parent, packages, data):
        super(CondaPackagesModel, self).__init__(parent)
        self._parent = parent
        self._packages = packages
        self._rows = data
        self._name_to_index = {r[C.COL_NAME]: i for i, r in enumerate(data)}

        palette = QPalette()
        self._palette = {
            'icon.upgrade.active': get_icon('conda_upgrade_active.png'),
            'icon.upgrade.inactive': get_icon('conda_upgrade_inactive.png'),
            'icon.upgrade.pressed': get_icon('conda_upgrade_pressed.png'),
            'icon.downgrade.active': get_icon('conda_downgrade_active.png'),
            'icon.downgrade.inactive': get_icon('conda_downgrade_inactive.png'),
            'icon.downgrade.pressed': get_icon('conda_downgrade_pressed.png'),
            'icon.add.active': get_icon('conda_add_active.png'),
            'icon.add.inactive': get_icon('conda_add_inactive.png'),
            'icon.add.pressed': get_icon('conda_add_pressed.png'),
            'icon.remove.active': get_icon('conda_remove_active.png'),
            'icon.remove.inactive': get_icon('conda_remove_inactive.png'),
            'icon.remove.pressed': get_icon('conda_remove_pressed.png'),
            'icon.action.not_installed': get_icon('conda_action_not_installed.png'),
            'icon.action.installed': get_icon('conda_action_installed.png'),
            'icon.action.installed_upgradable': get_icon('conda_action_installed_upgradable.png'),
            'icon.action.remove': get_icon('conda_action_remove.png'),
            'icon.action.add': get_icon('conda_action_add.png'),
            'icon.action.upgrade': get_icon('conda_action_upgrade.png'),
            'icon.action.downgrade': get_icon('conda_action_downgrade.png'),
            'icon.upgrade.arrow': get_icon('conda_upgrade_arrow.png'),
            'icon.python': get_icon('python.png').pixmap(QSize(16, 16)),
            'icon.anaconda': get_icon('anaconda.png').pixmap(QSize(16, 16)),
            'background.remove': QColor(128, 0, 0, 50),
            'background.install': QColor(0, 128, 0, 50),
            'background.upgrade': QColor(0, 0, 128, 50),
            'background.downgrade': QColor(128, 0, 128, 50),
            'foreground.not.installed': palette.color(QPalette.Mid),
            'foreground.upgrade': QColor(0, 0, 128, 255),
            }

    def _update_cell(self, row, column):
        start = self.index(row, column)
        end = self.index(row, column)
        self.dataChanged.emit(start, end)

    def update_style_palette(self, palette={}):
        if palette:
            self._palette.update(palette)

    def flags(self, index):
        """Override Qt method"""
        column = index.column()

        if index.isValid():
            if column in [C.COL_START, C.COL_END]:
                # return Qt.ItemFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                return Qt.ItemFlags(Qt.ItemIsEnabled)
            else:
                # return Qt.ItemFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                return Qt.ItemFlags(Qt.ItemIsEnabled)
        else:
            return Qt.ItemFlags(Qt.ItemIsEnabled)

    def data(self, index, role=Qt.DisplayRole):
        """Override Qt method"""
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return to_qvariant()

        row = index.row()
        column = index.column()

        P = self._palette

        if self._rows[row] == row:
            action = C.ACTION_NONE
            type_ = u''
            name = u''
            description = u''
            version = u'-'
            status = -1
            # url = u''
            # license_ = u''
            i = False
            r = False
            u = False
            d = False
            # action_version = None
        else:
            action = self._rows[row][C.COL_ACTION]
            type_ = self._rows[row][C.COL_PACKAGE_TYPE]
            name = self._rows[row][C.COL_NAME]
            description = self._rows[row][C.COL_DESCRIPTION]
            version = self._rows[row][C.COL_VERSION]
            status = self._rows[row][C.COL_STATUS]
            # url = self._rows[row][C.COL_URL]
            # license_ = self._rows[row][C.COL_LICENSE]
            i = self._rows[row][C.COL_INSTALL]
            r = self._rows[row][C.COL_REMOVE]
            u = self._rows[row][C.COL_UPGRADE]
            d = self._rows[row][C.COL_DOWNGRADE]
            # action_version = self._rows[row][C.COL_ACTION_VERSION]

        is_upgradable = self.is_upgradable(self.index(row, C.COL_VERSION))
#        if is_upgradable:
#            version += C.UPGRADE_SYMBOL

        if role == Qt.DisplayRole:
            if column == C.COL_PACKAGE_TYPE:
                return to_qvariant(type_)
            if column == C.COL_NAME:
                return to_qvariant(name)
            elif column == C.COL_VERSION:
                return to_qvariant(version)
            elif column == C.COL_STATUS:
                return to_qvariant(status)
            elif column == C.COL_DESCRIPTION:
                return to_qvariant(description)
            elif column == C.COL_ACTION:
                return to_qvariant(action)
        elif role == Qt.BackgroundRole:
            if action == C.ACTION_REMOVE:
                return to_qvariant(P['background.remove'])
            elif action == C.ACTION_INSTALL:
                return to_qvariant(P['background.install'])
            elif action == C.ACTION_UPGRADE:
                return to_qvariant(P['background.upgrade'])
            elif action == C.ACTION_DOWNGRADE:
                return to_qvariant(P['background.downgrade'])
        elif role == Qt.TextAlignmentRole:
            if column in [C.COL_NAME, C.COL_DESCRIPTION]:
                return to_qvariant(int(Qt.AlignLeft | Qt.AlignVCenter))
            elif column in [C.COL_VERSION] and is_upgradable:
                return to_qvariant(int(Qt.AlignLeft | Qt.AlignVCenter))
            else:
                return to_qvariant(int(Qt.AlignHCenter | Qt.AlignVCenter))
        elif role == Qt.DecorationRole:
            if column == C.COL_ACTION:
                if action == C.ACTION_NONE:
                    if status == C.NOT_INSTALLED:
                        return to_qvariant(P['icon.action.not_installed'])
                    elif status in [C.UPGRADABLE, C.MIXGRADABLE]:
                        return to_qvariant(P['icon.action.installed'])
                    elif status in [C.INSTALLED, C.DOWNGRADABLE,
                                    C.MIXGRADABLE]:
                        return to_qvariant(P['icon.action.installed'])
                elif action == C.ACTION_INSTALL:
                    return to_qvariant(P['icon.action.add'])
                elif action == C.ACTION_REMOVE:
                    return to_qvariant(P['icon.action.remove'])
                elif action == C.ACTION_UPGRADE:
                    return to_qvariant(P['icon.action.upgrade'])
                elif action == C.ACTION_DOWNGRADE:
                    return to_qvariant(P['icon.action.downgrade'])
                else:
                    return to_qvariant()
            elif column == C.COL_PACKAGE_TYPE:
                if type_ == C.CONDA_PACKAGE:
                    return to_qvariant(P['icon.anaconda'])
                elif type_ == C.PIP_PACKAGE:
                    return to_qvariant(P['icon.python'])
                else:
                    return to_qvariant()
            elif column == C.COL_INSTALL:
                if status == C.NOT_INSTALLED:
                    if i:
                        return to_qvariant(P['icon.add.pressed'])
                    else:
                        return to_qvariant(P['icon.add.active'])
                elif (status == C.INSTALLED or
                      status == C.UPGRADABLE or
                      status == C.DOWNGRADABLE or
                      status == C.MIXGRADABLE):
                    if r:
                        return to_qvariant(P['icon.remove.pressed'])
                    else:
                        return to_qvariant(P['icon.remove.active'])
                else:
                    return to_qvariant(P['icon.add.inactive'])
            elif column == C.COL_REMOVE:
                if (status == C.INSTALLED or
                    status == C.UPGRADABLE or
                    status == C.DOWNGRADABLE or
                   status == C.MIXGRADABLE):
                    if r:
                        return to_qvariant(P['icon.remove.pressed'])
                    else:
                        return to_qvariant(P['icon.remove.active'])
                else:
                    return to_qvariant(P['icon.remove.inactive'])
            elif column == C.COL_UPGRADE:
                if status == C.UPGRADABLE or \
                  status == C.MIXGRADABLE:
                    if u:
                        return to_qvariant(P['icon.upgrade.pressed'])
                    else:
                        return to_qvariant(P['icon.upgrade.active'])
                else:
                    return to_qvariant(P['icon.upgrade.inactive'])
            elif column == C.COL_DOWNGRADE:
                if status == C.DOWNGRADABLE or \
                  status == C.MIXGRADABLE:
                    if d:
                        return to_qvariant(P['icon.downgrade.pressed'])
                    else:
                        return to_qvariant(P['icon.downgrade.active'])
                else:
                    return to_qvariant(P['icon.downgrade.inactive'])
            elif column == C.COL_VERSION and is_upgradable:
                    return to_qvariant(P['icon.upgrade.arrow'])
        elif role == Qt.ToolTipRole:
            if column == C.COL_INSTALL and status == C.NOT_INSTALLED:
                return to_qvariant(_('Install package'))
            elif column == C.COL_INSTALL and (status == C.INSTALLED or
                                              status == C.UPGRADABLE or
                                              status == C.DOWNGRADABLE or
                                              status == C.MIXGRADABLE):
                return to_qvariant(_('Remove package'))
            elif column == C.COL_UPGRADE and (status == C.INSTALLED or
                                              status == C.UPGRADABLE or
                                              status == C.MIXGRADABLE):
                return to_qvariant(_('Upgrade package'))
            elif column == C.COL_DOWNGRADE and (status == C.INSTALLED or
                                                status == C.DOWNGRADABLE or
                                                status == C.MIXGRADABLE):
                return to_qvariant(_('Downgrade package'))
            elif column == C.COL_PACKAGE_TYPE:
                if type_ == C.CONDA_PACKAGE:
                    return to_qvariant(_('Conda package'))
                elif type_ == C.PIP_PACKAGE:
                    return to_qvariant(_('Python package'))
            elif column == C.COL_VERSION:
                if is_upgradable:
                    return to_qvariant(_('Update available'))
        elif role == Qt.ForegroundRole:
            palette = QPalette()
            if column in [C.COL_NAME, C.COL_DESCRIPTION]:
                if status in [C.INSTALLED, C.UPGRADABLE, C.DOWNGRADABLE,
                              C.MIXGRADABLE]:
                    color = palette.color(QPalette.WindowText)
                    return to_qvariant(color)
                elif status in [C.NOT_INSTALLED]:
                    color = palette.color(QPalette.Mid)
                    color = P['foreground.not.installed']
                    return to_qvariant(color)
            elif column in [C.COL_VERSION]:
                if is_upgradable:
                    return to_qvariant(P['foreground.upgrade'])

        elif role == Qt.SizeHintRole:
            if column in [C.ACTION_COLUMNS] + [C.COL_PACKAGE_TYPE]:
                return to_qvariant(QSize(24, 24))

        return to_qvariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Override Qt method"""
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return to_qvariant(int(Qt.AlignHCenter | Qt.AlignVCenter))
            return to_qvariant(int(Qt.AlignRight | Qt.AlignVCenter))
        elif role == Qt.ToolTipRole:
            column = section
            if column == C.COL_PACKAGE_TYPE:
                return to_qvariant(_('Package type: Conda, Pip'))
            elif column == C.COL_INSTALL:
                return to_qvariant(_('Install/Remove package'))
            elif column == C.COL_REMOVE:
                return to_qvariant(_('Remove package'))
            elif column == C.COL_UPGRADE:
                return to_qvariant(_('Upgrade package'))
            elif column == C.COL_DOWNGRADE:
                return to_qvariant(_('Downgrade package'))

        if orientation == Qt.Horizontal:
            if section == C.COL_PACKAGE_TYPE:
                return to_qvariant(_("T"))
            if section == C.COL_NAME:
                return to_qvariant(_("Name"))
            elif section == C.COL_VERSION:
                return to_qvariant(_("Version"))
            elif section == C.COL_DESCRIPTION:
                return to_qvariant(_("Description"))
            elif section == C.COL_STATUS:
                return to_qvariant(_("Status"))
            else:
                return to_qvariant()

    def rowCount(self, index=QModelIndex()):
        """Override Qt method"""
        return len(self._rows)

    def columnCount(self, index=QModelIndex()):
        """Override Qt method"""
        return len(C.COLUMNS)

    def row(self, rownum):
        """ """
        return self._rows[rownum]

    def first_index(self):
        """ """
        return self.index(0, 0)

    def last_index(self):
        """ """
        return self.index(self.rowCount() - 1, self.columnCount() - 1)

    def update_row_icon(self, row, column):
        """ """
        if column in C.ACTION_COLUMNS:
            r = self._rows[row]
            actual_state = r[column]
            r[column] = not actual_state
            self._rows[row] = r
            self._update_cell(row, column)

    def is_installable(self, model_index):
        """ """
        row = model_index.row()
        status = self._rows[row][C.COL_STATUS]
        return status == C.NOT_INSTALLED

    def is_removable(self, model_index):
        """ """
        row = model_index.row()
        status = self._rows[row][C.COL_STATUS]
        return status in [C.UPGRADABLE, C.DOWNGRADABLE, C.INSTALLED,
                          C.MIXGRADABLE]

    def is_upgradable(self, model_index):
        """ """
        row = model_index.row()
        status = self._rows[row][C.COL_STATUS]
        return status == C.UPGRADABLE or \
            status == C.MIXGRADABLE

    def is_downgradable(self, model_index):
        """ """
        row = model_index.row()
        status = self._rows[row][C.COL_STATUS]
        return status == C.DOWNGRADABLE or \
            status == C.MIXGRADABLE

    def action_status(self, model_index):
        """ """
        row = model_index.row()
        action_status = self._rows[row][C.COL_ACTION]
        return action_status

    def set_action_status(self, model_index, status, version=None):
        """
        """
        row = model_index.row()
        self._rows[row][C.COL_ACTION] = status
        self._rows[row][C.COL_ACTION_VERSION] = version
        self._update_cell(row, model_index.column())

    def clear_actions(self):
        """
        """
        for i, row in enumerate(self._rows):
            self._rows[i][C.COL_ACTION] = C.ACTION_NONE
            self._rows[i][C.COL_ACTION_VERSION] = None
            self._update_cell(i, C.COL_ACTION)
            self._update_cell(i, C.COL_ACTION_VERSION)

    def get_actions(self):
        """
        """
        dic = {C.CONDA_PACKAGE: {C.ACTION_INSTALL: [],
                                 C.ACTION_REMOVE: [],
                                 C.ACTION_UPGRADE: [],
                                 C.ACTION_DOWNGRADE: [],
                                 },
               C.PIP_PACKAGE: {C.ACTION_REMOVE: [],
                               }
               }

        for i, row in enumerate(self._rows):
            action = self._rows[i][C.COL_ACTION]
            name = self._rows[i][C.COL_NAME]
            type_ = self._rows[i][C.COL_PACKAGE_TYPE]
            action_version = self._rows[i][C.COL_ACTION_VERSION]
            current_version = self.get_package_version(name)

            if action != C.ACTION_NONE:
                version_from = current_version
                version_to = action_version
                dic[type_][action].append({'name': name,
                                           'version_from': version_from,
                                           'version_to': version_to,
                                           })
        return dic

    def get_package_versions(self, name):
        """
        Gives all the compatible package canonical name

        name : str
            Name of the package
        """
        package_data = self._packages.get(name)
        versions = []

        if package_data:
            versions = sort_versions(list(package_data.get('versions', [])))

        return versions

    def get_package_version(self, name):
        """  """
        if name in self._name_to_index:
            index = self._name_to_index[name]
            version = self.row(index)[C.COL_VERSION]
            return version.replace(C.UPGRADE_SYMBOL, '')
        else:
            return u''
