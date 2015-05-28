# -*- coding: utf-8 -*-
"""
Conda Packager Manager Widget.
"""

from __future__ import with_statement, print_function
import json
import gettext
import os
import os.path as osp
import platform
import shutil
import sys

from qtpy.QtCore import (QSize, Qt, QThread)
from qtpy.QtGui import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                        QProgressBar, QSpacerItem, QVBoxLayout, QWidget)

from ..models import Worker
from ..utils import conda_api_q, get_conf_path, get_module_data_path
from ..utils import constants as const
from ..utils.downloadmanager import DownloadManager
from ..utils.py3compat import configparser as cp
from ..widgets import CondaPackagesTable, SearchLineEdit
from ..widgets.dialogs import CondaPackageActionDialog


_ = gettext.gettext


class CondaPackagesWidget(QWidget):
    """Conda Packages Widget."""
    # Location of updated repo.json files from continuum/binstar
    CONDA_CONF_PATH = get_conf_path('repo')

    # Location of continuum/anaconda default repos shipped with conda-manager
    DATA_PATH = get_module_data_path()

    # file inside DATA_PATH with metadata for conda packages
    DATABASE_FILE = 'packages.ini'

    def __init__(self, parent):
        super(CondaPackagesWidget, self).__init__(parent)
        self._parent = parent
        self._status = ''  # Statusbar message
        self._conda_process = \
            conda_api_q.CondaProcess(self, self._on_conda_process_ready,
                                     self._on_conda_process_partial)
        self._prefix = conda_api_q.ROOT_PREFIX

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

        # TODO: Hardcoded channels for the moment
        self._default_channels = [
            ['_free_', 'http://repo.continuum.io/pkgs/free'],
            ['_pro_', 'http://repo.continuum.io/pkgs/pro']
            ]

        self._extra_channels = []
        # pyqt not working with ssl some bug here on the anaconda compilation
        # [['binstar_goanpeca_', 'https://conda.binstar.org/goanpeca']]

        self._repo_name = None   # linux-64, win-32, etc...
        self._channels = None    # [['filename', 'channel url'], ...]
        self._repo_files = None  # [filepath, filepath, ...]
        self._packages = {}
        self._download_error = None
        self._error = None

        # defined in self._setup() if None or in self.set_env method
        self._selected_env = None

        # widgets
        self.combobox_filter = QComboBox(self)
        self.button_update = QPushButton(_('Update package index'))
        self.textbox_search = SearchLineEdit(self)

        self.table = CondaPackagesTable(self)
        self.status_bar = QLabel(self)
        self.progress_bar = QProgressBar(self)

        self.widgets = [self.button_update, self.combobox_filter,
                        self.textbox_search, self.table]

        # setup widgets
        self.combobox_filter.addItems([k for k in
                                       const.COMBOBOX_VALUES_ORDERED])
        self.combobox_filter.setCurrentIndex(const.ALL)
        self.combobox_filter.setMinimumWidth(120)

        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setMaximumWidth(130)

        self.setWindowTitle(_("Conda Packages"))
        self.setMinimumSize(QSize(480, 300))

        # signals and slots
        self.combobox_filter.currentIndexChanged.connect(self.filter_package)
        self.button_update.clicked.connect(self.update_package_index)
        self.textbox_search.textChanged.connect(self.search_package)

        # NOTE: do not try to save the QSpacerItems in a variable for reuse
        # it will crash python on exit if you do!

        # layout setup
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

        self.setLayout(self._layout)
        # setup
        if self._supports_architecture():
            self.update_package_index()
            pass
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

    # --- callback download manager
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

        self._setup_widget()
    # ------------------------------------------------------------------------

    def _setup_widget(self):
        """ """
        if self._selected_env is None:
            self._selected_env = const.ROOT

        self._thread.terminate()
        self._thread = QThread(self)
        self._worker = Worker(self, self._repo_files, self._selected_env,
                              self._prefix)
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

    def _update_status(self, status=None, hide=True, progress=None):
        """Update status bar, progress bar display and widget visibility

        status : str
            TODO:
        hide : bool
            TODO:
        progress : [int, int]
            TODO:
        """
        for widget in self.widgets:
            widget.setDisabled(hide)

        self.progress_bar.setVisible(hide)

        if status is not None:
            self._status = status

        self.status_bar.setText(self._status)

        if progress is not None:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(progress[1])
            self.progress_bar.setValue(progress[0])

    def _run_action(self, name, action, version, versions):
        """ """
        env = self._selected_env
        dlg = CondaPackageActionDialog(self, env, name, action, version,
                                       versions)

        if dlg.exec_():
            dic = {}

            self.status = 'Processing'
            self._update_status(hide=True)
            self.repaint()

            env = self._selected_env
            ver1 = dlg.label_version.text()
            ver2 = dlg.combobox_version.currentText()
            pkg = u'{0}={1}{2}'.format(name, ver1, ver2)
            dep = dlg.checkbox.checkState()
            state = dlg.checkbox.isEnabled()
            dlg.close()

            dic['name'] = env
            dic['pkg'] = pkg
            dic['dep'] = not (dep == 0 and state)

            self._run_conda_process(action, dic)

    def _run_conda_process(self, action, dic):
        """ """
        cp = self._conda_process
        name = dic['name']

        if 'pkg' in dic and 'dep' in dic:
            pkgs = dic['pkg']
            dep = dic['dep']

        if action == const.INSTALL or action == const.UPGRADE or \
           action == const.DOWNGRADE:
            status = _('Installing <b>') + dic['pkg'] + '</b>'
            status = status + _(' into <i>') + dic['name'] + '</i>'
            cp.install(name=name, pkgs=[pkgs], dep=dep)
        elif action == const.REMOVE:
            status = (_('Removing <b>') + dic['pkg'] + '</b>' +
                      _(' from <i>') + dic['name'] + '</i>')
            cp.remove(pkgs, name=name)

    # --- actions to be implemented in case of environment needs
        elif action == const.CREATE:
            status = _('Creating environment <b>') + dic['name'] + '</b>'
        elif action == const.CLONE:
            status = (_('Cloning ') + '<i>' + dic['cloned from'] +
                      _('</i> into <b>') + dic['name'] + '</b>')
        elif action == const.REMOVE_ENV:
            status = _('Removing environment <b>') + dic['name'] + '</b>'

        self._update_status(hide=True, status=status, progress=[0, 0])

    def _on_conda_process_ready(self):
        """ """
        error = self._conda_process.error

        if error is None:
            status = _('there was an error')
            self._update_status(hide=False, status=status)
        else:
            self._update_status(hide=True)

        self._setup_widget()

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

    def set_environment(self, env):
        """Reset environent to reflect this environment in the pacakge model"""
        # TODO: check if env exists!
        self._selected_env = env
        self._setup_widget()

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


def test():
    """Run conda packages widget test"""
    from spyderlib.utils.qthelpers import qapplication
    app = qapplication()
    widget = CondaPackagesWidget(None)
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    test()
