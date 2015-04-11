

class CondaPackagesModel(QAbstractTableModel):
    """Abstract Model to handle the packages in a conda environment"""
    def __init__(self, parent, packages_names, packages_versions, row_data):
        super(CondaPackagesModel, self).__init__(parent)
        self._parent = parent
        self._packages_names = packages_names
        self._packages_versions = packages_versions
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
            'remove.pressed': get_icon('conda_remove_pressed.png')}

    def _update_cell(self, row, column):
        start = self.index(row, column)
        end = self.index(row, column)
        self.dataChanged.emit(start, end)

    def flags(self, index):
        """Override Qt method"""
        if not index.isValid():
            return Qt.ItemIsEnabled
        column = index.column()
        if column in (NAME, DESCRIPTION, VERSION):
            return Qt.ItemFlags(Qt.ItemIsEnabled)
        elif column in ACTION_COLUMNS:
            return Qt.ItemFlags(Qt.ItemIsEnabled)
        elif column == ENDCOL:
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
        if self._rows[row] == row:
            [name, description, version, status, url, license_, i, r, u, d] =\
                [u'', u'', '-', -1, u'', u'', False, False, False, False]
        else:
            [name, description, version, status, url, license_, i, r, u,
             d] = self._rows[row]

        if role == Qt.DisplayRole:
            if column == NAME:
                return to_qvariant(name)
            elif column == VERSION:
                return to_qvariant(version)
            elif column == STATUS:
                return to_qvariant(status)
            elif column == DESCRIPTION:
                return to_qvariant(description)
        elif role == Qt.TextAlignmentRole:
            if column in [NAME, DESCRIPTION]:
                return to_qvariant(int(Qt.AlignLeft | Qt.AlignVCenter))
            else:
                return to_qvariant(int(Qt.AlignHCenter | Qt.AlignVCenter))
        elif role == Qt.DecorationRole:
            if column == INSTALL:
                if status == NOT_INSTALLED:
                    if i:
                        return to_qvariant(self._icons['add.pressed'])
                    else:
                        return to_qvariant(self._icons['add.active'])
                else:
                    return to_qvariant(self._icons['add.inactive'])
            elif column == REMOVE:
                if (status == INSTALLED or status == UPGRADABLE or
                        status == DOWNGRADABLE or status == MIXGRADABLE):
                    if r:
                        return to_qvariant(self._icons['remove.pressed'])
                    else:
                        return to_qvariant(self._icons['remove.active'])
                else:
                    return to_qvariant(self._icons['remove.inactive'])
            elif column == UPGRADE:
                if status == UPGRADABLE or status == MIXGRADABLE:
                    if u:
                        return to_qvariant(self._icons['upgrade.pressed'])
                    else:
                        return to_qvariant(self._icons['upgrade.active'])
                else:
                    return to_qvariant(self._icons['upgrade.inactive'])
            elif column == DOWNGRADE:
                if status == DOWNGRADABLE or status == MIXGRADABLE:
                    if d:
                        return to_qvariant(self._icons['downgrade.pressed'])
                    else:
                        return to_qvariant(self._icons['downgrade.active'])
                else:
                    return to_qvariant(self._icons['downgrade.inactive'])
        elif role == Qt.ToolTipRole:
            if column == INSTALL and status == NOT_INSTALLED:
                return to_qvariant(_('Install package'))
            elif column == REMOVE and (status == INSTALLED or
                                       status == UPGRADABLE or
                                       status == DOWNGRADABLE or
                                       status == MIXGRADABLE):
                return to_qvariant(_('Remove package'))
            elif column == UPGRADE and (status == INSTALLED or
                                        status == UPGRADABLE or
                                        status == MIXGRADABLE):
                return to_qvariant(_('Upgrade package'))
            elif column == DOWNGRADE and (status == INSTALLED or
                                          status == DOWNGRADABLE or
                                          status == MIXGRADABLE):
                return to_qvariant(_('Downgrade package'))
        elif role == Qt.ForegroundRole:
            palette = QPalette()
            if column in [NAME, DESCRIPTION, VERSION]:
                if status in [INSTALLED, UPGRADABLE, DOWNGRADABLE,
                              MIXGRADABLE]:
                    color = palette.color(QPalette.WindowText)
                    return to_qvariant(color)
                elif status in [NOT_INSTALLED, NOT_INSTALLABLE]:
                    color = palette.color(QPalette.Mid)
                    return to_qvariant(color)
        return to_qvariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Override Qt method"""
        if role == Qt.TextAlignmentRole:
            if orientation == Qt.Horizontal:
                return to_qvariant(int(Qt.AlignHCenter | Qt.AlignVCenter))
            return to_qvariant(int(Qt.AlignRight | Qt.AlignVCenter))
        elif role == Qt.ToolTipRole:
            column = section
            if column == INSTALL:
                return to_qvariant(_('Install package'))
            elif column == REMOVE:
                return to_qvariant(_('Remove package'))
            elif column == UPGRADE:
                return to_qvariant(_('Upgrade package'))
            elif column == DOWNGRADE:
                return to_qvariant(_('Downgrade package'))

        if orientation == Qt.Horizontal:
            if section == NAME:
                return to_qvariant(_("Name"))
            elif section == VERSION:
                return to_qvariant(_("Version"))
            elif section == DESCRIPTION:
                return to_qvariant(_("Description"))
            elif section == STATUS:
                return to_qvariant(_("Status"))
            elif section == INSTALL:
                return to_qvariant(_("I"))
            elif section == REMOVE:
                return to_qvariant(_("R"))
            elif section == UPGRADE:
                return to_qvariant(_("U"))
            elif section == DOWNGRADE:
                return to_qvariant(_("D"))
            else:
                return to_qvariant()

    def rowCount(self, index=QModelIndex()):
        """Override Qt method"""
        return len(self._packages_names)

    def columnCount(self, index=QModelIndex()):
        """Override Qt method"""
        return len(COLUMNS)

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
        if column in ACTION_COLUMNS:
            r = self._rows[row]
            actual_state = r[column]
            r[column] = not actual_state
            self._rows[row] = r
            self._update_cell(row, column)

    def is_installable(self, model_index):
        """ """
        row = model_index.row()
        status = self._rows[row][STATUS]
        return status == NOT_INSTALLED

    def is_removable(self, model_index):
        """ """
        row = model_index.row()
        status = self._rows[row][STATUS]
        return status in [UPGRADABLE, DOWNGRADABLE, INSTALLED, MIXGRADABLE]

    def is_upgradable(self, model_index):
        """ """
        row = model_index.row()
        status = self._rows[row][STATUS]
        return status == UPGRADABLE or status == MIXGRADABLE

    def is_downgradable(self, model_index):
        """ """
        row = model_index.row()
        status = self._rows[row][STATUS]
        return status == DOWNGRADABLE or status == MIXGRADABLE

    def get_package_versions(self, name, versiononly=True):
        """ Gives all the compatible package canonical name

            name : str
                name of the package
            versiononly : bool
                if True, returns version number only, otherwise canonical name
        """
        versions = self._packages_versions
        if name in versions:
            if versiononly:
                ver = versions[name]
                temp = []
                for ve in ver:
                    n, v, b = conda_api_q.split_canonical_name(ve)
                    temp.append(v)
                return temp
            else:
                return versions[name]
        else:
            return []

    def get_package_version(self, name):
        """  """
        packages = self._packages_names
        if name in packages:
            rownum = packages.index(name)
            return self.row(rownum)[VERSION]
        else:
            return u''


class Worker(QObject):
    """ helper class to preprocess the repodata.json file(s) information into
    an usefull format for the CondaPackagesModel class without blocking the GUI
    in case the number of packages or channels grows too large
    """
    sig_ready = Signal()
    sig_status_updated = Signal(str, bool, list)

    def __init__(self, parent, repo_files, env, prefix):
        QObject.__init__(self)
        self._parent = parent
        self._repo_files = repo_files
        self._env = env
        self._prefix = prefix

        self.packages_names = None
        self.row_data = None
        self.packages_versions = None

        # define helper function locally
        self._get_package_metadata = parent.get_package_metadata

    def _prepare_model(self):
        """ """
        self._load_packages()
        self._setup_data()

    def _load_packages(self):
        """ """
        self.sig_status_updated.emit(_('Loading conda packages...'), True,
                                     [0, 0])
        grouped_usable_packages = {}
        packages_all = []

        for repo_file in self._repo_files:
            with open(repo_file, 'r') as f:
                data = json.load(f)

            # info = data['info']
            packages = data['packages']

            if packages is not None:
                packages_all.append(packages)
                for key in packages:
                    val = packages[key]
                    name = val['name'].lower()
                    grouped_usable_packages[name] = list()

        for packages in packages_all:
            for key in packages:
                val = packages[key]
                name = val['name'].lower()
                grouped_usable_packages[name].append([key, val])

        self._packages = grouped_usable_packages

    def _setup_data(self):
        """ """
        self._packages_names = []
        self._rows = []
        self._packages_versions = {}  # the canonical name of versions compat

        self._packages_linked = {}
        self._packages_versions_number = {}
        self._packages_versions_all = {}  # the canonical name of all versions
        self._packages_upgradable = {}
        self._packages_downgradable = {}
        self._packages_installable = {}
        self._packages_licenses_all = {}
        self._conda_api = conda_api_q

        cp = self._conda_api
        # TODO: Do we want to exclude some packages? If we plan to continue
        # with the projects in spyder idea, we might as well hide spyder
        # from the possible instalable apps...
        # exclude_names = ['emptydummypackage']  # FIXME: packages to exclude?

        # First do the list of linked packages so in case there is no json
        # We can show at least that
        self._packages_linked = {}
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

        pybuild = 'py' + ''.join(pyver.split('.'))[:-1] + '_'  # + pybuild
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
            
            # fix error when package installed from other channels besides
            # the standard ones
            if n in self._packages_versions_number:
                vers = self._packages_versions_number[n]
                vers = sort_versions(list(set(vers)), reverse=True)
    
                self._packages_upgradable[n] = not current_ver == vers[0]
                self._packages_downgradable[n] = not current_ver == vers[-1]

        for row, name in enumerate(self._packages_names):
            if name in self._packages_linked:
                version = self._packages_linked[name][1]
                if (self._packages_upgradable[name] and
                        self._packages_downgradable[name]):
                    status = MIXGRADABLE
                elif self._packages_upgradable[name]:
                    status = UPGRADABLE
                elif self._packages_downgradable[name]:
                    status = DOWNGRADABLE
                else:
                    status = INSTALLED
            else:
                vers = self._packages_versions_number[name]
                vers = sort_versions(list(set(vers)), reverse=True)
                version = '-'

                if len(vers) == 0:
                    status = NOT_INSTALLABLE
                else:
                    status = NOT_INSTALLED

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

            self._rows[row] = [name, description, version, status, url,
                               license_, False, False, False, False]

        self.row_data = self._rows
        self.packages_names = self._packages_names
        self.packages_versions = self._packages_versions

        self.sig_ready.emit()


