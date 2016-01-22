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
import json

# Third party imports
from qtpy.compat import to_qvariant
from qtpy.QtCore import (QAbstractTableModel, QObject, Qt, Signal,
                         QModelIndex, QSize)
from qtpy.QtGui import QPalette

# Local imports
from conda_manager.utils import conda_api_q, get_icon, sort_versions
from conda_manager.utils import constants as C

_ = gettext.gettext


class CondaPackagesModel(QAbstractTableModel):
    """Abstract Model to handle the packages in a conda environment"""
    def __init__(self, parent, packages_names, packages_versions,
                 packages_sizes, row_data):
        super(CondaPackagesModel, self).__init__(parent)
        self._parent = parent
        self._packages_names = packages_names
        self._packages_versions = packages_versions
        self._packages_sizes = packages_sizes
        self._rows = row_data

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
                elif status in [C.NOT_INSTALLED, C.NOT_INSTALLABLE]:
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
#            elif section == C.COL_INSTALL:
#                return to_qvariant(_("I/R"))
#            elif section == C.COL_REMOVE:
#                return to_qvariant(_("R"))
#            elif section == C.COL_UPGRADE:
#                return to_qvariant(_("U"))
#            elif section == C.COL_DOWNGRADE:
#                return to_qvariant(_("D"))
            else:
                return to_qvariant()

    def rowCount(self, index=QModelIndex()):
        """Override Qt method"""
        return len(self._packages_names)

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

    def get_package_versions(self, name, versiononly=True):
        """
        Gives all the compatible package canonical name

        name : str
            name of the package
        versiononly : bool
            if `True`, returns version number only, otherwise canonical name
        """
        versions = self._packages_versions
        if name in versions:
            if versiononly:
                ver = versions[name]
                temp = []
                for ve in ver:
                    n, v, b = conda_api_q.CondaProcess.split_canonical_name(ve)
                    temp.append(v)
                return sort_versions(list(set(temp)))
            else:
                return versions[name]
        else:
            return []

    def get_package_version(self, name):
        """  """
        packages = self._packages_names
        if name in packages:
            rownum = packages.index(name)
            return self.row(rownum)[C.COL_VERSION]
        else:
            return u''


class PackagesWorker(QObject):
    """
    Helper class to preprocess the repodata.json file(s) information into
    an usefull format for the CondaPackagesModel class without blocking the UI
    in case the number of packages or channels grows too large.
    """
    sig_ready = Signal()
    sig_status_updated = Signal(str, bool, list)

    def __init__(self, parent, repo_files, prefix, root_prefix, pip_packages):
        QObject.__init__(self)
        self._parent = parent
        self._repo_files = repo_files
        self._prefix = prefix
        self._root_prefix = root_prefix
        self._pip_packages_names = {}

        for p in pip_packages:
            n, v, b = conda_api_q.CondaProcess.split_canonical_name(p)
            local = ''
            if '(' in n:
                name = n.split('-(')
                n = name[0]
                local = name[-1].replace(')', '')
            self._pip_packages_names[n] = {}
            self._pip_packages_names[n]['version'] = v
            self._pip_packages_names[n]['local'] = local
            self._pip_packages_names[n]['build'] = b

        self.packages_names = None
        self.row_data = None
        self.packages_versions = None
        self._packages = None

        # Define helper function locally
        self._get_package_metadata = parent.get_package_metadata

    def _prepare_model(self):
        """ """
        if self._repo_files:
            self._load_packages()
            self._setup_data()

    def _load_packages(self):
        """ """
        self.sig_status_updated.emit(_('Loading conda packages...'), True,
                                     [0, 0])
        grouped_usable_packages = {}
        packages_all = []

        for repo_file in self._repo_files:
            repo_file = repo_file.replace('.bz2', '')
            with open(repo_file, 'r') as f:
                data = json.load(f)

            # info = data['info']
            packages = data['packages']

            if packages is not None:
                packages_all.append(packages)
                for key in packages:
                    val = packages[key]
                    name = val['name'].lower()
                    if name not in grouped_usable_packages:
                        grouped_usable_packages[name] = []

        # Add linked packages
        cp = conda_api_q.CondaProcess
        canonical_names = sorted(list(cp.linked(self._prefix)))
        for canonical_name in canonical_names:
            n, v, b = cp.split_canonical_name(canonical_name)
            name = n.lower()
            grouped_usable_packages[name] = []

        # Add from repo
        for packages in packages_all:
            for key in packages:
                val = packages[key]
                name = val['name'].lower()
                grouped_usable_packages[name].append([key, val])

        # Add pip packages
        for name in self._pip_packages_names:
            grouped_usable_packages[name] = []

        self._packages = grouped_usable_packages

    def _setup_data(self):
        """ """
        self._packages_names = []
        self._rows = []
        self._packages_versions = {}  # the canonical name of versions compat

        self._packages_linked = {}
        self._packages_versions_number = {}
        self._packages_versions_all = {}  # the canonical name of all versions
        self._packages_sizes_all = {}
        self._packages_upgradable = {}
        self._packages_downgradable = {}
        self._packages_installable = {}
        self._packages_licenses_all = {}
        self._conda_api = conda_api_q.CondaProcess

        cp = self._conda_api
        # TODO: Do we want to exclude some packages? If we plan to continue
        # with the projects in spyder idea, we might as well hide spyder
        # from the possible instalable apps...
        # exclude_names = ['emptydummypackage']  # FIXME: packages to exclude?

        # First do the list of linked packages so in case there is no json
        # We can show at least that
        self._packages_linked = {}

        # FIXME: move this logic outside...?
        canonical_names = sorted(list(cp.linked(self._prefix)))

        # This has to do with the versions of the selected environment, NOT
        # with the python version running!
        pyver, numpyver, pybuild, numpybuild = None, None, None, None
        for canonical_name in canonical_names:
            n, v, b = cp.split_canonical_name(canonical_name)
            self._packages_linked[n] = [n, v, b, canonical_name]
            if n == 'python':
                pyver = v
                pybuild = b
            elif n == 'numpy':
                numpyver = v
                numpybuild = b

        if self._packages == {}:
            self._packages_names = sorted([l for l in self._packages_linked])
            self._rows = list(range(len(self._packages_names)))
            for n in self._packages_linked:
                val = self._packages_linked[n]
                v = val[-1]
                self._packages[n] = [[v, v]]
        else:
            self._packages_names = sorted([key for key in
                                           self._packages])
            self._rows = list(range(len(self._packages_names)))
            for n in self._packages:
                self._packages_licenses_all[n] = {}

            for n in self._packages:
                self._packages_sizes_all[n] = {}

        pybuild = 'py' + ''.join(pyver.split('.')[:-1]) + '_'  # + pybuild
        if numpyver is None and numpybuild is None:
            numpybuild = ''
        else:
            numpybuild = 'np' + ''.join(numpyver.split('.'))[:-1]

        for n in self._packages_names:
            self._packages_versions_all[n] = \
                sort_versions([s[0] for s in self._packages[n]],
                              reverse=True)
            for s in self._packages[n]:
                val = s[1]
                if 'version' in val:
                    ver = val['version']
                    if 'license' in val:
                        lic = val['license']
                        self._packages_licenses_all[n][ver] = lic
                    if 'size' in val:
                        size = val['size']
                        self._packages_sizes_all[n][ver] = size


        # Now clean versions depending on the build version of python and numpy
        # FIXME: there is an issue here... at this moment a package with same
        # version but only differing in the build number will get added
        # Now it assumes that there is a python installed in the root
        for name in self._packages_versions_all:
            tempver_cano = []
            tempver_num = []
            for ver in self._packages_versions_all[name]:
                n, v, b = cp.split_canonical_name(ver)

                if 'np' in b and 'py' in b:
                    if numpybuild + pybuild in b:
                        tempver_cano.append(ver)
                        tempver_num.append(v)
                elif 'py' in b:
                    if pybuild in b:
                        tempver_cano.append(ver)
                        tempver_num.append(v)
                elif 'np' in b:
                    if numpybuild in b:
                        tempver_cano.append(ver)
                        tempver_num.append(v)
                else:
                    tempver_cano.append(ver)
                    tempver_num.append(v)

            self._packages_versions[name] = sort_versions(tempver_cano,
                                                          reverse=True)
            self._packages_versions_number[name] = sort_versions(tempver_num,
                                                                 reverse=True)

        # FIXME: Check what to do with different builds??
        # For the moment here a set is used to remove duplicate versions
        for n in self._packages_linked:
            vals = self._packages_linked[n]
            canonical_name = vals[-1]
            current_ver = vals[1]

            # Fix error when package installed from other channels besides
            # the standard ones
            if n in self._packages_versions_number:
                vers = self._packages_versions_number[n]
                vers = sort_versions(list(set(vers)), reverse=True)

                # If no other version is available just give a dummy version
                if not vers:
                    vers = [-1]
                self._packages_upgradable[n] = not current_ver == vers[0]
                self._packages_downgradable[n] = not current_ver == vers[-1]

        for row, name in enumerate(self._packages_names):
            if name in self._packages_linked:
                version = self._packages_linked[name][1]
                if self._packages[name] == []:
                    # Package not in actual channels
                    status = C.INSTALLED
                elif (self._packages_upgradable[name] and
                        self._packages_downgradable[name]):
                    status = C.MIXGRADABLE
                elif self._packages_upgradable[name]:
                    status = C.UPGRADABLE
                elif self._packages_downgradable[name]:
                    status = C.DOWNGRADABLE
                else:
                    status = C.INSTALLED
            else:
                vers = self._packages_versions_number[name]
                vers = sort_versions(list(set(vers)), reverse=True)
                version = '-'

                if len(vers) == 0:
                    status = C.NOT_INSTALLABLE
                else:
                    status = C.NOT_INSTALLED

            metadata = self._get_package_metadata(name)
            description = metadata['description']
            url = metadata['url']

            if version in self._packages_licenses_all[name]:
                if self._packages_licenses_all[name][version]:
                    license_ = self._packages_licenses_all[name][version]
                else:
                    license_ = u''
            else:
                license_ = u''

            # TODO: Temporal fix to include pip packages
            if name in self._pip_packages_names:
                type_ = C.PIP_PACKAGE
                status = C.INSTALLED
                version = self._pip_packages_names[name]['version']
            else:
                type_ = C.CONDA_PACKAGE

            # For look purposes the first column is empty
            self._rows[row] = [0, type_, name, description, version, status, url,
                               license_, False, False, False, False]

        self.row_data = self._rows
        self.packages_names = self._packages_names
        self.packages_versions = self._packages_versions
        self.packages_sizes = self._packages_sizes_all
        self.sig_ready.emit()
