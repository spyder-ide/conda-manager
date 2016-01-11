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
from qtpy.QtCore import Qt, QAbstractTableModel, QModelIndex
from qtpy.QtGui import QFont

# Local imports
from conda_manager.utils import conda_api_q

_ = gettext.gettext


class CondaDependenciesModel(QAbstractTableModel):
    """ """
    def __init__(self, parent, dic):
        super(CondaDependenciesModel, self).__init__(parent)
        self._parent = parent
        self._packages = dic
        self._rows = []
        self._bold_rows = []

        if len(dic) == 0:
            self._rows = [[_(u'Updating dependency list...'), u'', u'', u'']]
            self._bold_rows.append(0)
        else:
            if 'actions' in dic:
                dic = dic['actions']

            titles = [_('Name'), _('Unlink'), _('Link'), _('Download')]
            order = ['UNLINK', 'LINK', 'FETCH']
            packages_dic = self._build_packages_table(dic)
            packages_order = sorted(list(packages_dic))

            rows = [titles]
            self._bold_rows.append(0)
            for package in packages_order:
                row = [package]
                item = packages_dic[package]
                for section in order:
                    row.append(item.get(section, u'-'))
                rows.append(row)

            for row in rows:
                self._rows.append(row)

    def _build_packages_table(self, dic):
        """ """
        sections = {'FETCH': None,
                    'EXTRACT': None,
                    'LINK': None,
                    'UNLINK': None}
        packages = {}

        for section in sections:
            sections[section] = dic.get(section, ())
            if sections[section]:
                for item in sections[section]:
                    i = item.split(' ')[0]
                    name, version, build = conda_api_q.CondaProcess.split_canonical_name(i)
                    packages[name] = {}

        for section in sections:
            pkgs = sections[section]
            for item in pkgs:
                i = item.split(' ')[0]
                name, version, build = conda_api_q.CondaProcess.split_canonical_name(i)
                packages[name][section] = version
        return packages

    def flags(self, index):
        """Override Qt method"""
        if not index.isValid():
            return Qt.ItemIsEnabled
        column = index.column()
        if column in [0, 1, 2, 3]:
            return Qt.ItemFlags(Qt.ItemIsEnabled)
        else:
            return Qt.ItemFlags(Qt.NoItemFlags)

    def data(self, index, role=Qt.DisplayRole):
        """Override Qt method"""
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return to_qvariant()
        row = index.row()
        column = index.column()

        # Carefull here with the order, this has to be adjusted manually
        if self._rows[row] == row:
            name, unlink, link, fetch = [u'', u'', u'', u'']
        else:
            name, unlink, link, fetch = self._rows[row]

        if role == Qt.DisplayRole:
            if column == 0:
                return to_qvariant(name)
            elif column == 1:
                return to_qvariant(unlink)
            elif column == 2:
                return to_qvariant(link)
            elif column == 3:
                return to_qvariant(fetch)
        elif role == Qt.TextAlignmentRole:
            if column in [0]:
                return to_qvariant(int(Qt.AlignLeft | Qt.AlignVCenter))
            elif column in [1, 2, 3]:
                return to_qvariant(int(Qt.AlignHCenter | Qt.AlignVCenter))
        elif role == Qt.ForegroundRole:
            return to_qvariant()
        elif role == Qt.FontRole:
            font = QFont()
            if row in self._bold_rows:
                font.setBold(True)
                return to_qvariant(font)
            else:
                font.setBold(False)
                return to_qvariant(font)
        return to_qvariant()

    def rowCount(self, index=QModelIndex()):
        """Override Qt method"""
        return len(self._rows)

    def columnCount(self, index=QModelIndex()):
        """Override Qt method"""
        return 4

    def row(self, rownum):
        """ """
        return self._rows[rownum]
