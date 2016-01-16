# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""
Conda Packager Manager Widget.
"""

# Standard library imports
from __future__ import (absolute_import, division, print_function,
                        unicode_literals, with_statement)
import json
import gettext
import os
import os.path as osp
import platform
import shutil
import sys


# Third party imports
from qtpy.QtCore import (QSize, Qt, QThread, Signal)
from qtpy.QtGui import (QComboBox, QDialogButtonBox, QDialog, QHBoxLayout,
                        QLabel, QMessageBox, QPushButton, QProgressBar,
                        QSpacerItem, QVBoxLayout, QWidget)

# Local imports
from conda_manager.models import PackagesWorker
from conda_manager.utils import (conda_api_q, get_conf_path,
                                 get_module_data_path)
from conda_manager.utils import constants as const
from conda_manager.utils.downloadmanager import DownloadManager
from conda_manager.utils.py3compat import configparser as cp
from conda_manager.widgets import CondaPackagesTable, SearchLineEdit
from conda_manager.widgets.dialogs import CondaPackageActionDialog


_ = gettext.gettext


class CondaPackagesWidget(QWidget):
    """Conda Packages Widget."""
    # Location of updated repo.json files from continuum/binstar
    CONDA_CONF_PATH = get_conf_path('repo')

    # Location of continuum/anaconda default repos shipped with conda-manager
    DATA_PATH = get_module_data_path()

    # file inside DATA_PATH with metadata for conda packages
    DATABASE_FILE = 'packages.ini'

    sig_worker_ready = Signal()
    sig_packages_ready = Signal()
    sig_environment_created = Signal()

    def __init__(self, parent, name=None, prefix=None, channels=[]):
        super(CondaPackagesWidget, self).__init__(parent)
        self._parent = parent
        self._status = ''  # Statusbar message
        self._conda_process = conda_api_q.CondaProcess(self)
        self._root_prefix = self._conda_process.ROOT_PREFIX
        self._prefix = None
        self._temporal_action_dic = {}
        self._download_manager = DownloadManager(self,
                                                 self._on_download_finished,
                                                 self._on_download_progress,
                                                 self.CONDA_CONF_PATH)
        self._thread = QThread(self)
        self._worker = None
        self._db_metadata = cp.ConfigParser()
        self._db_file = CondaPackagesWidget.DATABASE_FILE
        self._db_metadata.readfp(open(osp.join(self.DATA_PATH, self._db_file)))
        self._packages_names = None
        self._row_data = None
        self._hide_widgets = False

        # TODO: Hardcoded channels for the moment
        self._default_channels = [
            ['_free_', 'http://repo.continuum.io/pkgs/free'],
            #['_pro_', 'http://repo.continuum.io/pkgs/pro']
            ]

        self._extra_channels = channels
        # pyqt not working with ssl some bug here on the anaconda compilation
        # [['binstar_goanpeca_', 'https://conda.binstar.org/goanpeca']]

        self._repo_name = None   # linux-64, win-32, etc...
        self._channels = None    # [['filename', 'channel url'], ...]
        self._repo_files = None  # [filepath, filepath, ...]
        self._packages = {}
        self._download_error = None
        self._error = None

        # Widgets
        self.combobox_filter = QComboBox(self)
        self.button_update = QPushButton(_('Update package index'))
        self.textbox_search = SearchLineEdit(self)

        self.table = CondaPackagesTable(self)
        self.status_bar = QLabel(self)
        self.progress_bar = QProgressBar(self)

        self.button_ok = QPushButton(_('Ok'))

        self.bbox = QDialogButtonBox(Qt.Horizontal)
        self.bbox.addButton(self.button_ok, QDialogButtonBox.ActionRole)

        self.widgets = [self.button_update, self.combobox_filter,
                        self.textbox_search, self.table, self.button_ok]

        # Widgets setup
        self.combobox_filter.addItems([k for k in
                                       const.COMBOBOX_VALUES_ORDERED])
        self.combobox_filter.setMinimumWidth(120)
        self.button_ok.setDefault(True)
        self.button_ok.setAutoDefault(True)
        self.button_ok.setVisible(False)

        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setMaximumWidth(130)

        self.setWindowTitle(_("Conda Package Manager"))
        self.setMinimumSize(QSize(480, 300))

        # Signals and slots
        self.combobox_filter.currentIndexChanged.connect(self.filter_package)
        self.button_update.clicked.connect(self.update_package_index)
        self.textbox_search.textChanged.connect(self.search_package)
        self._conda_process.sig_partial.connect(self._on_conda_process_partial)
        self._conda_process.sig_finished.connect(self._on_conda_process_ready)

        # NOTE: do not try to save the QSpacerItems in a variable for reuse
        # it will crash python on exit if you do!

        # Layout
        self._spacer_w = 250
        self._spacer_h = 5

        self._top_layout = QHBoxLayout()
        self._top_layout.addWidget(self.combobox_filter)
        self._top_layout.addWidget(self.button_update)
        self._top_layout.addWidget(self.textbox_search)

        self._middle_layout = QVBoxLayout()
        self._middle_layout.addWidget(self.table)

        self._bottom_layout = QHBoxLayout()
        self._bottom_layout.addWidget(self.status_bar, Qt.AlignLeft)
        self._bottom_layout.addWidget(self.progress_bar, Qt.AlignRight)

        self._layout = QVBoxLayout(self)
        self._layout.addItem(QSpacerItem(self._spacer_w, self._spacer_h))
        self._layout.addLayout(self._top_layout)
        self._layout.addLayout(self._middle_layout)
        self._layout.addItem(QSpacerItem(self._spacer_w, self._spacer_h))
        self._layout.addLayout(self._bottom_layout)
        self._layout.addItem(QSpacerItem(self._spacer_w, self._spacer_h))
        self._layout.addWidget(self.bbox)
        self._layout.addItem(QSpacerItem(self._spacer_w, self._spacer_h))

        self.setLayout(self._layout)

        # Setup
        self.set_environment(name=name, prefix=prefix, update=False)
        if self._supports_architecture():
            self.update_package_index()
        else:
            status = _('no packages supported for this architecture!')
            self._update_status(progress=[0, 0], hide=True, status=status)

    def _supports_architecture(self):
        """ """
        self._set_repo_name()

        if self._repo_name is None:
            return False
        else:
            return True

    def _set_repo_name(self):
        """Get python system and bitness, and return default repo name"""
        system = sys.platform.lower()
        bitness = 64 if sys.maxsize > 2**32 else 32
        machine = platform.machine()
        fname = [None, None]

        if 'win' in system:
            fname[0] = 'win'
        elif 'lin' in system:
            fname[0] = 'linux'
        elif 'osx' in system or 'darwin' in system:  # TODO: is this correct?
            fname[0] = 'osx'
        else:
            return None

        if bitness == 32:
            fname[1] = '32'
        elif bitness == 64:
            fname[1] = '64'
        else:
            return None

        # armv6l
        if machine.startswith('armv6'):
            fname[1] = 'armv6l'

        if None in fname:
            self._repo_name = None
        else:
            self._repo_name = '-'.join(fname)

    def _set_channels(self):
        """ """
        default = self._default_channels
        extra = self._extra_channels
        body = self._repo_name
        tail = '/repodata.json'
        channels = []
        files = []

        for channel in default + extra:
            prefix = channel[0]
            url = '{0}/{1}{2}'.format(channel[1], body, tail)
            name = '{0}{1}.json'.format(prefix, body)
            channels.append([name, url])
            files.append(osp.join(self.CONDA_CONF_PATH, name))

        self._repo_files = files
        self._channels = channels

    def _download_repodata(self):
        """download the latest version available of the repo(s)"""
        status = _('Updating package index...')
        self._update_status(hide=True, progress=[0, 0], status=status)

        self._download_manager.set_queue(self._channels)
        self._download_manager.start_download()

    # --- Callback download manager
    # ------------------------------------------------------------------------
    def _on_download_progress(self, progress):
        """function called by download manager when receiving data

        progress : [int, int]
            A two item list of integers with relating [downloaded, total]
        """
        self._update_status(hide=True, progress=progress, status=None)

    def _on_download_finished(self):
        """function called by download manager when finished all downloads

        this will be called even if errors were encountered, so error handling
        is done here as well
        """
        error = self._download_manager.get_errors()

        if error is not None:
            self._update_status(hide=False)

            if not osp.isdir(self.CONDA_CONF_PATH):
                os.mkdir(self.CONDA_CONF_PATH)

            for repo_file in self._repo_files:
                # if a file does not exists, look for one in DATA_PATH
                if not osp.isfile(repo_file):
                    filename = osp.basename(repo_file)
                    bck_repo_file = osp.join(self.DATA_PATH, filename)

                    # if available copy to CONDA_CONF_PATH
                    if osp.isfile(bck_repo_file):
                        shutil.copy(bck_repo_file, repo_file)
                    # otherwise remove from the repo_files list
                    else:
                        self._repo_files.remove(repo_file)
            self._error = None

        self.setup_packages()

    # ------------------------------------------------------------------------
    def setup_packages(self):
        """ """
        pip_packages = self._conda_process.pip_list(prefix=self._prefix)
        self._thread.terminate()
        self._thread = QThread(self)
        self._worker = PackagesWorker(self, self._repo_files,
                                      self._prefix, self._root_prefix,
                                      pip_packages)
        self._worker.sig_status_updated.connect(self._update_status)
        self._worker.sig_ready.connect(self._worker_ready)
        self._worker.sig_ready.connect(self._thread.quit)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker._prepare_model)
        self._thread.start()

    def _worker_ready(self):
        """ """
        self._packages_names = self._worker.packages_names
        self._packages_versions = self._worker.packages_versions
        self._row_data = self._worker.row_data

        # depending on the size of table this might lock the gui for a moment
        self.table.setup_model(self._packages_names, self._packages_versions,
                               self._row_data)
        self.table.filter_changed()

        self._update_status(hide=False)
        self.filter_package(const.INSTALLED)
        self.sig_worker_ready.emit()
        self.sig_packages_ready.emit()

    def _update_status(self, status=None, hide=True, progress=None, env=False):
        """Update status bar, progress bar display and widget visibility

        status : str
            TODO:
        hide : bool
            TODO:
        progress : [int, int]
            TODO:
        """
        self.busy = hide
        for widget in self.widgets:
            widget.setDisabled(hide)

        self.progress_bar.setVisible(hide)

        if status is not None:
            self._status = status

        if self._prefix == self._root_prefix:
            short_env = 'root'
        elif self._conda_process.environment_exists(prefix=self._prefix):
            short_env = osp.basename(self._prefix)
        else:
            short_env = self._prefix

        if env:
            self._status = '{0} (<b>{1}</b>)'.format(self._status,
                                                     short_env)
        self.status_bar.setText(self._status)

        if progress is not None:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(progress[1])
            self.progress_bar.setValue(progress[0])

    def _run_action(self, package_name, action, version, versions):
        """ """
        prefix = self._prefix
        dlg = CondaPackageActionDialog(self, prefix, package_name, action,
                                       version, versions)

        if dlg.exec_():
            dic = {}

            self.status = 'Processing'
            self._update_status(hide=True)
            self.repaint()

            ver1 = dlg.label_version.text()
            ver2 = dlg.combobox_version.currentText()
            pkg = u'{0}={1}{2}'.format(package_name, ver1, ver2)
            dep = dlg.checkbox.checkState()
            state = dlg.checkbox.isEnabled()
            dlg.close()

            dic['pkg'] = pkg
            dic['dep'] = not (dep == 0 and state)
            dic['action'] = None
            self._run_conda_process(action, dic)

    def _run_conda_process(self, action, dic):
        """ """
        cp = self._conda_process
        prefix = self._prefix

        if prefix == self._root_prefix:
            name = 'root'
        elif self._conda_process.environment_exists(prefix=prefix):
            name = osp.basename(prefix)
        else:
            name = prefix

        if 'pkg' in dic and 'dep' in dic:
            pkgs = dic['pkg']
            if not isinstance(pkgs, list):
                pkgs = [pkgs]
            dep = dic['dep']

        if action == const.INSTALL or action == const.UPGRADE or \
           action == const.DOWNGRADE:
            status = _('Installing <b>') + dic['pkg'] + '</b>'
            status = status + _(' into <i>') + name + '</i>'
            cp.install(prefix=prefix, pkgs=pkgs, dep=dep)
        elif action == const.REMOVE:
            status = (_('moving <b>') + dic['pkg'] + '</b>' +
                      _(' from <i>') + name + '</i>')
            cp.remove(pkgs[0], prefix=prefix)

        # --- Actions to be implemented in case of environment needs
        elif action == const.CREATE:
            status = _('Creating environment <b>') + name + '</b>'
            cp.create(prefix=prefix, pkgs=pkgs)
        elif action == const.CLONE:
            status = (_('Cloning ') + '<i>' + dic['cloned from'] +
                      _('</i> into <b>') + name + '</b>')
        elif action == const.REMOVE_ENV:
            status = _('Removing environment <b>') + name + '</b>'

        self._update_status(hide=True, status=status, progress=[0, 0])
        self._temporal_action_dic = dic

    def _on_conda_process_ready(self):
        """ """
        error = self._conda_process.error

        if error is None:
            status = _('there was an error')
            self._update_status(hide=False, status=status)
        else:
            self._update_status(hide=True)

        dic = self._temporal_action_dic
        if dic['action'] == const.CREATE:
            self.sig_environment_created.emit()
        self.setup_packages()

    def _on_conda_process_partial(self):
        """ """
        try:
            partial = self._conda_process.partial.split('\n')[0]
            partial = json.loads(partial)
        except:
            partial = {'progress': 0, 'maxval': 0}

        progress = partial['progress']
        maxval = partial['maxval']

        if 'fetch' in partial:
            status = _('Downloading <b>') + partial['fetch'] + '</b>'
        elif 'name' in partial:
            status = _('Installing and linking <b>') + partial['name'] + '</b>'
        else:
            progress = 0
            maxval = 0
            status = None

        self._update_status(status=status, progress=[progress, maxval])

    # Public api
    # ----------
    def get_package_metadata(self, name):
        """ """
        db = self._db_metadata
        metadata = dict(description='', url='', pypi='', home='', docs='',
                        dev='')
        for key in metadata:
            name_lower = name.lower()
            for name_key in (name_lower, name_lower.split('-')[0]):
                try:
                    metadata[key] = db.get(name_key, key)
                    break
                except (cp.NoSectionError, cp.NoOptionError):
                    pass
        return metadata

    def update_package_index(self):
        """ """
        self._set_channels()
        self._download_repodata()

    def search_package(self, text):
        """ """
        self.table.search_string_changed(text)

    def filter_package(self, value):
        """ """
        self.table.filter_status_changed(value)

    def set_environment(self, name=None, prefix=None, update=True):
        """ """
        if name and prefix:
            raise Exception('#TODO:')

        if name and self._conda_process.environment_exists(name=name):
            self._prefix = self.get_prefix_envname(name)
        elif prefix and self._conda_process.environment_exists(prefix=prefix):
            self._prefix = prefix
        else:
            self._prefix = self._root_prefix

        # Reset environent to reflect this environment in the package model
        if update:
            self.setup_packages()

    def get_environment_prefix(self):
        """Returns the active environment prefix."""
        return self._prefix

    def get_environment_name(self):
        """
        Returns the active environment name if it is located in the default
        conda environments directory, otherwise it returns the prefix.
        """
        name = osp.basename(self._prefix)

        if not (name and self._conda_process.environment_exists(name=name)):
            name = self._prefix

        return name

    def get_environments(self):
        """
        Get a list of conda environments located in the default conda
        environments directory.
        """
        return self._conda_process.get_envs()

    def get_prefix_envname(self, name):
        """Returns the prefix for a given environment by name."""
        return self._conda_process.get_prefix_envname(name)

    def get_package_versions(self, name):
        """ """
        return self.table.source_model.get_package_versions(name)

    def create_environment(self, name=None, prefix=None, packages=['python']):
        """ """
        # If environment exists already? GUI should take care of this
        # BUT the api call should simply set that env as the env
        dic = {}
        dic['name'] = name
        dic['pkg'] = packages
        dic['dep'] = True  # Not really needed but for the moment!
        dic['action'] = const.CREATE
        self._run_conda_process(const.CREATE, dic)

    def enable_widgets(self):
        """ """
        self.table.hide_columns()

    def disable_widgets(self):
        """ """
        self.table.hide_action_columns()


class CondaPackagesDialog(QDialog, CondaPackagesWidget):
    """Conda packages dialog."""
    sig_worker_ready = Signal()
    sig_packages_ready = Signal()
    sig_environment_created = Signal()

    def __init__(self, parent=None, name=None, prefix=None, channels=[]):
        super(CondaPackagesDialog, self).__init__(parent=parent,
                                                  name=name,
                                                  prefix=prefix,
                                                  channels=channels)
        self.button_ok.setVisible(True)

        self.button_ok.clicked.connect(self.accept)

    def reject(self):
        """ """
        if self.busy:
            answer = QMessageBox.question(
                self,
                'Quit Conda Manager?',
                'Conda is still busy.\n\nDo you want to quit?',
                buttons=QMessageBox.Yes | QMessageBox.No)

            if answer == QMessageBox.Yes:
                QDialog.reject(self)
                # Do some cleanup?
        else:
            QDialog.reject(self)


# TODO:  update packages.ini file
# TODO: Define some automatic tests that can include the following:

# Test 1
# Find out if all the urls in the packages.ini file lead to a webpage
# or if they produce a 404 error

# Test 2
# Test installation of custom packages

# Test 3
# nothing is loaded on the package listing but clicking on it will produce an
# nonetype error


def test_widget():
    """Run conda packages widget test"""
    from conda_manager.utils.qthelpers import qapplication
    app = qapplication()
    widget = CondaPackagesWidget(None)
    widget.show()
    sys.exit(app.exec_())


def test_dialog():
    """Run conda packages widget test"""
    from conda_manager.utils.qthelpers import qapplication
    app = qapplication()
    dialog = CondaPackagesDialog(name='root')
    dialog.exec_()
    sys.exit(app.exec_())

if __name__ == '__main__':
    test_dialog()
#    test_widget()
