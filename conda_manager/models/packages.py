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
from qtpy.QtGui import QPalette

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

        self._icons = {
            'upgrade.active': get_icon('conda_upgrade_active.png'),
            'upgrade.inactive': get_icon('conda_upgrade_inactive.png'),
            'upgrade.pressed': get_icon('conda_upgrade_pressed.png'),
            'downgrade.active': get_icon('conda_downgrade_active.png'),
            'downgrade.inactive': get_icon('conda_downgrade_inactive.png'),
            'downgrade.pressed': get_icon('conda_downgrade_pressed.png'),
            'add.active': get_icon('conda_add_active.png'),
            'add.inactive': get_icon('conda_add_inactive.png'),
            'add.pressed': get_icon('conda_add_pressed.png'),
            'remove.active': get_icon('conda_remove_active.png'),
            'remove.inactive': get_icon('conda_remove_inactive.png'),
            'remove.pressed': get_icon('conda_remove_pressed.png'),
            'python': get_icon('python.png'),
            'anaconda': get_icon('anaconda.png'),
            }

    def _update_cell(self, row, column):
        start = self.index(row, column)
        end = self.index(row, column)
        self.dataChanged.emit(start, end)

    def flags(self, index):
        """Override Qt method"""
        if not index.isValid():
            return Qt.ItemIsEnabled

        column = index.column()
        if column in (C.COL_PACKAGE_TYPE, C.COL_NAME, C.COL_DESCRIPTION,
                      C.COL_VERSION):
            return Qt.ItemFlags(Qt.ItemIsEnabled)
        elif column in C.ACTION_COLUMNS:
            return Qt.ItemFlags(Qt.ItemIsEnabled)
        elif column == C.COL_END:
            return Qt.ItemFlags(Qt.NoItemFlags)
        else:
            return Qt.ItemFlags(Qt.ItemIsEnabled)

    def data(self, index, role=Qt.DisplayRole):
        """Override Qt method"""
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return to_qvariant()

        row = index.row()
        column = index.column()

        # Carefull here with the order, this has to be adjusted manually
        # For look purposes the first column is empty
        if self._rows[row] == row:
            [__, type_, name, description, version, status, url, license_, i, r, u, d] = [0, u'', u'', '-', -1, u'', u'', False, False, False, False]
        else:
            [__, type_, name, description, version, status, url, license_, i, r, u, d] = self._rows[row]

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
        elif role == Qt.TextAlignmentRole:
            if column in [C.COL_NAME, C.COL_DESCRIPTION]:
                return to_qvariant(int(Qt.AlignLeft | Qt.AlignVCenter))
            else:
                return to_qvariant(int(Qt.AlignHCenter | Qt.AlignVCenter))
        elif role == Qt.DecorationRole:
            if column == C.COL_PACKAGE_TYPE:
                if type_ == C.CONDA_PACKAGE:
                    return to_qvariant(self._icons['anaconda'])
                elif type_ == C.PIP_PACKAGE:
                    return to_qvariant(self._icons['python'])
                else:
                    return to_qvariant()
            elif column == C.COL_INSTALL:
                if status == C.NOT_INSTALLED:
                    if i:
                        return to_qvariant(self._icons['add.pressed'])
                    else:
                        return to_qvariant(self._icons['add.active'])
                elif (status == C.INSTALLED or
                      status == C.UPGRADABLE or
                      status == C.DOWNGRADABLE or
                      status == C.MIXGRADABLE):
                    if r:
                        return to_qvariant(self._icons['remove.pressed'])
                    else:
                        return to_qvariant(self._icons['remove.active'])
                else:
                    return to_qvariant(self._icons['add.inactive'])

            elif column == C.COL_REMOVE:
                if (status == C.INSTALLED or
                    status == C.UPGRADABLE or
                    status == C.DOWNGRADABLE or
                   status == C.MIXGRADABLE):
                    if r:
                        return to_qvariant(self._icons['remove.pressed'])
                    else:
                        return to_qvariant(self._icons['remove.active'])
                else:
                    return to_qvariant(self._icons['remove.inactive'])
            elif column == C.COL_UPGRADE:
                if status == C.UPGRADABLE or \
                  status == C.MIXGRADABLE:
                    if u:
                        return to_qvariant(self._icons['upgrade.pressed'])
                    else:
                        return to_qvariant(self._icons['upgrade.active'])
                else:
                    return to_qvariant(self._icons['upgrade.inactive'])
            elif column == C.COL_DOWNGRADE:
                if status == C.DOWNGRADABLE or \
                  status == C.MIXGRADABLE:
                    if d:
                        return to_qvariant(self._icons['downgrade.pressed'])
                    else:
                        return to_qvariant(self._icons['downgrade.active'])
                else:
                    return to_qvariant(self._icons['downgrade.inactive'])
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
        elif role == Qt.ForegroundRole:
            palette = QPalette()
            if column in [C.COL_NAME, C.COL_DESCRIPTION, C.COL_VERSION]:
                if status in [C.INSTALLED, C.UPGRADABLE, C.DOWNGRADABLE,
                              C.MIXGRADABLE]:
                    color = palette.color(QPalette.WindowText)
                    return to_qvariant(color)
                elif status in [C.NOT_INSTALLED]:
                    color = palette.color(QPalette.Mid)
                    return to_qvariant(color)

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
            return self.row(index)[C.COL_VERSION]
        else:
            return u''
