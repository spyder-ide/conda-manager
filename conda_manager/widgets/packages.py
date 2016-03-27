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
                        with_statement)
from collections import deque
import json
import gettext
import os.path as osp
import sys

# Third party imports
from qtpy.QtCore import QEvent, QSize, Qt, Signal
from qtpy.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout,
                            QMessageBox, QPushButton, QVBoxLayout, QWidget)

# Local imports
from conda_manager.api import ManagerAPI
from conda_manager.utils import get_conf_path, get_module_data_path
from conda_manager.utils import constants as C
from conda_manager.utils.logs import logger
from conda_manager.utils.py3compat import configparser as cp
from conda_manager.widgets import (ButtonPackageApply, ButtonPackageCancel,
                                   ButtonPackageChannels, ButtonPackageClear,
                                   ButtonPackageOk, ButtonPackageUpdate,
                                   DropdownPackageFilter, FramePackageBottom,
                                   FramePackageTop, LabelPackageStatus,
                                   ProgressBarPackage,
                                   )

from conda_manager.widgets.dialogs.actions import CondaPackageActionDialog
from conda_manager.widgets.dialogs.channels import DialogChannels
from conda_manager.widgets.dialogs.close import ClosePackageManagerDialog
from conda_manager.widgets.helperwidgets import LineEditSearch
from conda_manager.widgets.table import TableCondaPackages


_ = gettext.gettext


class FirstRowWidget(QPushButton):
    """
    Widget located before pacakges table to handle focus in and tab focus
    on the table correctly.
    """
    sig_enter_first = Signal()

    def __init__(self, widget_before=None):
        QPushButton.__init__(self)
        self.widget_before = widget_before

    def sizeHint(self):
        return QSize(0, 0)

    def focusInEvent(self, event):
        self.sig_enter_first.emit()

    def event(self, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key in [Qt.Key_Tab]:
                self.sig_enter_first.emit()
                return True
            else:
                return QPushButton.event(self, event)
        else:
            return QPushButton.event(self, event)


class LastRowWidget(QPushButton):
    """
    Widget located after pacakges table to handle focus out and backtab focus
    on the table correctly.
    """
    sig_enter_last = Signal()

    def __init__(self, widgets_after=None):
        QPushButton.__init__(self)
        self.widgets_after = widgets_after

    def focusInEvent(self, event):
        self.sig_enter_last.emit()

    def add_focus_widget(self, widget):
        if widget in self.widgets_after:
            return
        else:
            self.widgets_after[-1] = widget

    def handle_tab(self):
        for w in self.widgets_after:
            if w.isVisible():
                w.setFocus()
                return

    def event(self, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key in [Qt.Key_Backtab]:
                self.sig_enter_last.emit()
                return True
            else:
                return QPushButton.event(self, event)
        else:
            return QPushButton.event(self, event)

    def sizeHint(self):
        return QSize(0, 0)


class CondaPackagesWidget(QWidget):
    """
    Conda Packages Widget.
    """

    # Location of updated repo.json files from continuum/binstar
    CONDA_CONF_PATH = get_conf_path('repo')

    # Location of continuum/anaconda default repos shipped with conda-manager
    DATA_PATH = get_module_data_path()

    # file inside DATA_PATH with metadata for conda packages
    DATABASE_FILE = 'packages.ini'

    sig_worker_ready = Signal()
    sig_packages_ready = Signal()
    sig_environment_created = Signal(object, object)
    sig_environment_removed = Signal(object, object)
    sig_environment_cloned = Signal(object, object)
    sig_channels_updated = Signal(tuple, tuple)  # channels, active_channels
    sig_process_cancelled = Signal()
    sig_next_focus = Signal()
    sig_packages_busy = Signal()

    def __init__(self,
                 parent,
                 name=None,
                 prefix=None,
                 channels=(),
                 active_channels=(),
                 conda_url='https://conda.anaconda.org',
                 conda_api_url='https://api.anaconda.org',
                 setup=True,
                 data_directory=None,
                 extra_metadata={}):

        super(CondaPackagesWidget, self).__init__(parent)

        # Check arguments: active channels, must be witbhin channels
        for ch in active_channels:
            if ch not in channels:
                raise Exception("'active_channels' must be also within "
                                "'channels'")

        if data_directory is None:
            data_directory = self.CONDA_CONF_PATH

        self._parent = parent
        self._current_action_name = ''
        self._hide_widgets = False
        self._metadata = extra_metadata  # From repo.continuum
        self._metadata_links = {}        # Bundled metadata
        self.api = ManagerAPI()
        self.busy = False
        self.data_directory = data_directory
        self.conda_url = conda_url
        self.conda_api_url = conda_api_url
        self.name = name
        self.package_blacklist = []
        self.prefix = prefix
        self.root_prefix = self.api.ROOT_PREFIX
        self.style_sheet = None
        self.message = ''
        self.apply_actions_dialog = None
        self.conda_errors = []
        self.message_box_error = None
        self.token = None

        if channels:
            self._channels = channels
            self._active_channels = active_channels
        else:
            self._channels = self.api.conda_get_condarc_channels()
            self._active_channels = self._channels[:]

        # Widgets
        self.cancel_dialog = ClosePackageManagerDialog
        self.bbox = QDialogButtonBox(Qt.Horizontal)
        self.button_cancel = ButtonPackageCancel('Cancel')
        self.button_channels = ButtonPackageChannels(_('Channels'))
        self.button_ok = ButtonPackageOk(_('Ok'))
        self.button_update = ButtonPackageUpdate(_('Update package index...'))
        self.button_apply = ButtonPackageApply(_('Apply'))
        self.button_clear = ButtonPackageClear(_('Clear'))
        self.combobox_filter = DropdownPackageFilter(self)
        self.frame_top = FramePackageTop()
        self.frame_bottom = FramePackageTop()
        self.progress_bar = ProgressBarPackage(self)
        self.status_bar = LabelPackageStatus(self)
        self.table = TableCondaPackages(self)
        self.textbox_search = LineEditSearch(self)
        self.widgets = [self.button_update, self.button_channels,
                        self.combobox_filter, self.textbox_search, self.table,
                        self.button_ok, self.button_apply, self.button_clear]
        self.table_first_row = FirstRowWidget(
            widget_before=self.textbox_search)
        self.table_last_row = LastRowWidget(
            widgets_after=[self.button_apply, self.button_clear,
                           self.button_cancel, self.combobox_filter])

        # Widgets setup
        for button in [self.button_cancel, self.button_apply,
                       self.button_clear, self.button_ok, self.button_update,
                       self.button_channels]:
            button.setDefault(True)
        max_height = self.status_bar.fontMetrics().height()
        max_width = self.textbox_search.fontMetrics().width('M'*23)
        self.bbox.addButton(self.button_ok, QDialogButtonBox.ActionRole)
        self.button_ok.setAutoDefault(True)
        self.button_ok.setDefault(True)
        self.button_ok.setMaximumSize(QSize(0, 0))
        self.button_ok.setVisible(False)
        self.button_channels.setCheckable(True)
        self.combobox_filter.addItems([k for k in C.COMBOBOX_VALUES_ORDERED])
        self.combobox_filter.setMinimumWidth(120)
        self.progress_bar.setMaximumHeight(max_height*1.2)
        self.progress_bar.setMaximumWidth(max_height*12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.setMinimumSize(QSize(480, 300))
        self.setWindowTitle(_("Conda Package Manager"))
        self.status_bar.setFixedHeight(max_height*1.5)
        self.textbox_search.setMaximumWidth(max_width)
        self.textbox_search.setPlaceholderText('Search Packages')
        self.table_first_row.setMaximumHeight(0)
        self.table_last_row.setMaximumHeight(0)
        self.table_last_row.setVisible(False)
        self.table_first_row.setVisible(False)

        # Layout
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.combobox_filter)
        top_layout.addWidget(self.button_channels)
        top_layout.addWidget(self.button_update)
        top_layout.addWidget(self.textbox_search)
        top_layout.addStretch()
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.frame_top.setLayout(top_layout)

        middle_layout = QVBoxLayout()
        middle_layout.addWidget(self.table_first_row)
        middle_layout.addWidget(self.table)
        middle_layout.addWidget(self.table_last_row)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.status_bar)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.progress_bar)
        bottom_layout.addWidget(self.button_cancel)
        bottom_layout.addWidget(self.button_apply)
        bottom_layout.addWidget(self.button_clear)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.frame_bottom.setLayout(bottom_layout)

        layout = QVBoxLayout(self)
        layout.addWidget(self.frame_top)
        layout.addLayout(middle_layout)
        layout.addWidget(self.frame_bottom)
        self.setLayout(layout)

        self.setTabOrder(self.combobox_filter, self.button_channels)
        self.setTabOrder(self.button_channels, self.button_update)
        self.setTabOrder(self.button_update, self.textbox_search)
        self.setTabOrder(self.textbox_search, self.table_first_row)
        self.setTabOrder(self.table, self.table_last_row)
        self.setTabOrder(self.table_last_row, self.button_apply)
        self.setTabOrder(self.button_apply, self.button_clear)
        self.setTabOrder(self.button_clear, self.button_cancel)

        # Signals and slots
        self.api.sig_repodata_updated.connect(self._repodata_updated)
        self.combobox_filter.currentIndexChanged.connect(self.filter_package)
        self.button_apply.clicked.connect(self.apply_multiple_actions)
        self.button_clear.clicked.connect(self.clear_actions)
        self.button_cancel.clicked.connect(self.cancel_process)
        self.button_channels.clicked.connect(self.show_channels_dialog)
        self.button_update.clicked.connect(self.update_package_index)
        self.textbox_search.textChanged.connect(self.search_package)
        self.table.sig_conda_action_requested.connect(self._run_conda_action)
        self.table.sig_actions_updated.connect(self.update_actions)
        self.table.sig_pip_action_requested.connect(self._run_pip_action)
        self.table.sig_status_updated.connect(self.update_status)
        self.table.sig_next_focus.connect(self.table_last_row.handle_tab)
        self.table.sig_previous_focus.connect(
            lambda: self.table_first_row.widget_before.setFocus())
        self.table_first_row.sig_enter_first.connect(self._handle_tab_focus)
        self.table_last_row.sig_enter_last.connect(self._handle_backtab_focus)

        # Setup
        self.api.client_set_domain(conda_api_url)
        self.api.set_data_directory(self.data_directory)
        self._load_bundled_metadata()
        self.update_actions(0)

        if setup:
            self.set_environment(name=name, prefix=prefix)
            self.setup()

    # --- Helpers
    # -------------------------------------------------------------------------
    def _handle_tab_focus(self):
        self.table.setFocus()
        if self.table.proxy_model:
            index = self.table.proxy_model.index(0, 0)
            self.table.setCurrentIndex(index)

    def _handle_backtab_focus(self):
        self.table.setFocus()
        if self.table.proxy_model:
            row = self.table.proxy_model.rowCount() - 1
            index = self.table.proxy_model.index(row, 0)
            self.table.setCurrentIndex(index)

    # --- Callbacks
    # -------------------------------------------------------------------------
    def _load_bundled_metadata(self):
        """
        """
        logger.debug('')

        parser = cp.ConfigParser()
        db_file = CondaPackagesWidget.DATABASE_FILE
        with open(osp.join(self.DATA_PATH, db_file)) as f:
            parser.readfp(f)

        for name in parser.sections():
            metadata = {}
            for key, data in parser.items(name):
                metadata[key] = data
            self._metadata_links[name] = metadata

    def _setup_packages(self, worker, data, error):
        """
        """
        if error:
            logger.error(error)
        else:
            logger.debug('')

        combobox_index = self.combobox_filter.currentIndex()
        status = C.PACKAGE_STATUS[combobox_index]

        packages = worker.packages

        # Remove blacklisted packages
        for package in self.package_blacklist:
            if package in packages:
                packages.pop(package)
            for i, row in enumerate(data):
                if package == data[i][C.COL_NAME]:
                    data.pop(i)

        self.table.setup_model(packages, data, self._metadata_links)
        self.combobox_filter.setCurrentIndex(combobox_index)
        self.filter_package(status)

        if self._current_model_index:
            self.table.setCurrentIndex(self._current_model_index)
            self.table.verticalScrollBar().setValue(self._current_table_scroll)

        if error:
            self.update_status(error, False)
        self.sig_packages_ready.emit()
        self.table.setFocus()

    def get_logged_user_list_channels(self):
        channels = []
        for ch in self._active_channels:
            if self.conda_url in ch and 'repo.continuum' not in ch:
                channel = ch.split('/')[-1]
                channels.append(channel)
        return channels

    def _prepare_model_data(self, worker=None, output=None, error=None):
        """
        """
        if error:
            logger.error(error)
        else:
            logger.debug('')

        packages, apps = output
#        worker = self.api.pip_list(prefix=self.prefix)
#        worker.sig_finished.connect(self._pip_list_ready)
        logins = self.get_logged_user_list_channels()
        worker = self.api.client_multi_packages(logins=logins,
                                                access='private')
        worker.sig_finished.connect(self._user_private_packages_ready)
        worker.packages = packages
        worker.apps = apps

    def _user_private_packages_ready(self, worker, output, error):
        if error:
            logger.error(error)
        else:
            logger.debug('')

        packages = worker.packages
        apps = worker.apps
        worker = self.api.pip_list(prefix=self.prefix)
        worker.sig_finished.connect(self._pip_list_ready)
        worker.packages = packages
        worker.apps = apps

#        private_packages = {}
#        if output:
#            all_private_packages = output
#            for item in all_private_packages:
#                name = item.get('name', '')
#                public = item.get('public', True)
#                package_types = item.get('package_types', [])
#                latest_version = item.get('latest_version', '')
#                if name and not public and 'conda' in package_types:
#                    private_packages[name] = {'versions': item.get('versions', []),
#                                              'app_entry': {},
#                                              'type': {},
#                                              'size': {},
#                                              'latest_version': latest_version,
#                                              }
        worker.private_packages = output

    def _pip_list_ready(self, worker, pip_packages, error):
        """
        """
        if error:
            logger.error(error)
        else:
            logger.debug('')

        packages = worker.packages
        private_packages = worker.private_packages
        linked_packages = self.api.conda_linked(prefix=self.prefix)
        data = self.api.client_prepare_packages_data(packages,
                                                     linked_packages,
                                                     pip_packages,
                                                     private_packages)

        combobox_index = self.combobox_filter.currentIndex()
        status = C.PACKAGE_STATUS[combobox_index]

        # Remove blacklisted packages
        for package in self.package_blacklist:
            if package in packages:
                packages.pop(package)

            for i, row in enumerate(data):
                if package == data[i][C.COL_NAME]:
                    data.pop(i)

        self.table.setup_model(packages, data, self._metadata_links)
        self.combobox_filter.setCurrentIndex(combobox_index)
        self.filter_package(status)

        if self._current_model_index:
            self.table.setCurrentIndex(self._current_model_index)
            self.table.verticalScrollBar().setValue(self._current_table_scroll)

        if error:
            self.update_status(str(error), False)
        self.sig_packages_ready.emit()
        self.table.setFocus()

    def _repodata_updated(self, paths):
        """
        """
        worker = self.api.client_load_repodata(paths, extra_data={},
                                               metadata=self._metadata)
        worker.paths = paths
        worker.sig_finished.connect(self._prepare_model_data)

    def _metadata_updated(self, worker, path, error):
        """
        """
        if error:
            logger.error(error)
        else:
            logger.debug('')

        if path and osp.isfile(path):
            with open(path, 'r') as f:
                data = f.read()
            try:
                self._metadata = json.loads(data)
            except Exception:
                self._metadata = {}
        else:
            self._metadata = {}
        self.api.update_repodata(self._channels)

    # ---
    # -------------------------------------------------------------------------
    def _run_multiple_actions(self, worker=None, output=None, error=None):
        """
        """
        logger.error(str(error))

        if output and isinstance(output, dict):
            conda_error_type = output.get('error_type', None)
            conda_error = output.get('error', None)

            if conda_error_type or conda_error:
                self.conda_errors.append((conda_error_type, conda_error))
                logger.error((conda_error_type, conda_error))

        if self._multiple_process:
            status, func = self._multiple_process.popleft()
            self.update_status(status)
            worker = func()
            worker.sig_finished.connect(self._run_multiple_actions)
            worker.sig_partial.connect(self._partial_output_ready)
        else:
            if self.conda_errors and self.message_box_error:
                text = "The following errors occured:"
                error = ''
                for conda_error in self.conda_errors:
                    error += str(conda_error[0]) + ':\n'
                    error += str(conda_error[1]) + '\n\n'
                dlg = self.message_box_error(text=text, error=error,
                                             title='Conda process error')
                dlg.setMinimumWidth(400)
                dlg.exec_()

            self.update_status('', hide=False)
            self.setup()

    def _pip_process_ready(self, worker, output, error):
        """
        """
        if error is not None:
            status = _('there was an error')
            self.update_status(hide=False, message=status)
        else:
            self.update_status(hide=True)

        self.setup()

    def _conda_process_ready(self, worker, output, error):
        """
        """
        if error is not None:
            status = _('there was an error')
            self.update_status(hide=False, message=status)
        else:
            self.update_status(hide=True)

        conda_error = None
        conda_error_type = None
        if output and isinstance(output, dict):
            conda_error_type = output.get('error_type')
            conda_error = output.get('error')

            if conda_error_type or conda_error:
                logger.error((conda_error_type, conda_error))

        dic = self._temporal_action_dic

        if dic['action'] == C.ACTION_CREATE:
            self.sig_environment_created.emit(conda_error, conda_error_type)
        elif dic['action'] == C.ACTION_CLONE:
            self.sig_environment_cloned.emit(conda_error, conda_error_type)
        elif dic['action'] == C.ACTION_REMOVE_ENV:
            self.sig_environment_removed.emit(conda_error, conda_error_type)

        self.setup()

    def _partial_output_ready(self, worker, output, error):
        """
        """
        message = None
        progress = (0, 0)

        if isinstance(output, dict):
            progress = (output.get('progress', None),
                        output.get('maxval', None))
            name = output.get('name', None)
            fetch = output.get('fetch', None)

            if fetch:
                message = "Downloading <b>{0}</b>...".format(fetch)

            if name:
                self._current_action_name = name
                message = "Linking <b>{0}</b>...".format(name)

        logger.debug(message)
        self.update_status(message, progress=progress)

    def _run_pip_action(self, package_name, action):
        """
        DEPRECATED
        """
        prefix = self.prefix

        if prefix == self.root_prefix:
            name = 'root'
        elif self.api.conda_environment_exists(prefix=prefix):
            name = osp.basename(prefix)
        else:
            name = prefix

        if action == C.ACTION_REMOVE:
            msgbox = QMessageBox.question(self,
                                          "Remove pip package: "
                                          "{0}".format(package_name),
                                          "Do you want to proceed?",
                                          QMessageBox.Yes | QMessageBox.No)
            if msgbox == QMessageBox.Yes:
                self.update_status()
                worker = self.api.pip_remove(prefix=self.prefix,
                                             pkgs=[package_name])
                worker.sig_finished.connect(self._pip_process_ready)
                status = (_('Removing pip package <b>') + package_name +
                          '</b>' + _(' from <i>') + name + '</i>')
                self.update_status(hide=True, message=status,
                                   progress=[0, 0])

    def _run_conda_action(self, package_name, action, version, versions,
                          packages_sizes):
        """
        DEPRECATED
        """
        prefix = self.prefix
        dlg = CondaPackageActionDialog(self, prefix, package_name, action,
                                       version, versions, packages_sizes,
                                       self._active_channels)

        if dlg.exec_():
            dic = {}

            self.status = 'Processing'
            self.update_status(hide=True)
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
        """
        DEPRECTAED
        """
        self._temporal_action_dic = dic
#        prefix = self.prefix
#
#        if prefix == self.root_prefix:
#            name = 'root'
#        elif self.api.conda_environment_exists(prefix=prefix):
#            name = osp.basename(prefix)
#        else:
#            name = prefix

        if 'pkgs' in dic and 'dep' in dic:
            dep = dic['dep']
            pkgs = dic['pkgs']
            if not isinstance(pkgs, list):
                pkgs = [pkgs]

#        if (action == C.ACTION_INSTALL or action == C.ACTION_UPGRADE or
#           action == C.ACTION_DOWNGRADE):
#            status = _('Installing <b>') + dic['pkg'] + '</b>'
#            status = status + _(' into <i>') + name + '</i>'
#            worker = self.api.conda_install(prefix=prefix, pkgs=pkgs, dep=dep,
#                                            channels=self._active_channels)
#        elif action == C.ACTION_REMOVE:
#            status = (_('Removing <b>') + dic['pkg'] + '</b>' +
#                      _(' from <i>') + name + '</i>')
#            worker = self.api.conda_remove(pkgs[0], prefix=prefix)

        # --- Environment management actions
        name = dic['name']
        if action == C.ACTION_CREATE:
            status = _('Creating environment <b>') + name + '</b>'
            worker = self.api.conda_create(name=name, pkgs=pkgs,
                                           channels=self._active_channels)
        elif action == C.ACTION_CLONE:
            clone = dic['clone']
            status = (_('Cloning ') + '<i>' + clone +
                      _('</i> into <b>') + name + '</b>')
            worker = self.api.conda_clone(clone, name=name)
        elif action == C.ACTION_REMOVE_ENV:
            status = _('Removing environment <b>') + name + '</b>'
            worker = self.api.conda_remove(name=name, all_=True)

        worker.sig_finished.connect(self._conda_process_ready)
        worker.sig_partial.connect(self._partial_output_ready)
        self.update_status(hide=True, message=status, progress=None)
        self._temporal_action_dic = dic
        return worker

    # Public API
    # -------------------------------------------------------------------------
    def prepare_model_data(self, packages, apps):
        """
        """
        logger.debug('')
        self._prepare_model_data(output=(packages, apps))

    # These should be private methods....
    def enable_widgets(self):
        """ """
        self.table.hide_columns()

    def disable_widgets(self):
        """ """
        self.table.hide_action_columns()

    def accept_channels_dialog(self):
        self.button_channels.setFocus()
        self.button_channels.toggle()

    def update_actions(self, number_of_actions):
        """
        """
        self.button_apply.setVisible(bool(number_of_actions))
        self.button_clear.setVisible(bool(number_of_actions))

    # --- Non UI API
    # -------------------------------------------------------------------------
    def setup(self, check_updates=False, blacklist=[], metadata={}):
        """
        Setup packages.

        Main triger method to download repodata, load repodata, prepare and
        updating the data model.

        Parameters
        ----------
        check_updates : bool
            If `True`, checks that the latest repodata is available on the
            listed channels. If `False`, the data will be loaded from the
            downloaded files without checking for newer versions.
        blacklist: list of str
            List of conda package names to be excluded from the actual package
            manager view.
        """
        self.sig_packages_busy.emit()

        if self.busy:
            logger.debug('Busy...')
            return
        else:
            logger.debug('')

        if blacklist:
            self.package_blacklist = [p.lower() for p in blacklist]

        if metadata:
            self._metadata = metadata

        self._current_model_index = self.table.currentIndex()
        self._current_table_scroll = self.table.verticalScrollBar().value()
        self.update_status('Updating package index', True)

        if check_updates:
            worker = self.api.update_metadata()
            worker.sig_finished.connect(self._metadata_updated)
        else:
            paths = self.api.repodata_files(channels=self._active_channels)
            self._repodata_updated(paths)

    def update_domains(self, anaconda_api_url=None, conda_url=None):
        """
        """
        logger.debug(str((anaconda_api_url, conda_url)))
        update = False

        if anaconda_api_url:
            if self.conda_api_url != anaconda_api_url:
                update = True

            self.conda_api_url = anaconda_api_url
            self.api.client_set_domain(anaconda_api_url)

        if conda_url:
            if self.conda_url != conda_url:
                update = True
            self.conda_url = conda_url

        if update:
            pass

    def set_environment(self, name=None, prefix=None):
        """
        This does not update the package manager!
        """
        logger.debug(str((name, prefix)))

        if prefix and self.api.conda_environment_exists(prefix=prefix):
            self.prefix = prefix
        elif name and self.api.conda_environment_exists(name=name):
            self.prefix = self.get_prefix_envname(name)
        else:
            self.prefix = self.root_prefix

    def set_token(self, token):
        self.token = token

    def update_channels(self, channels, active_channels):
        """
        """
        logger.debug(str((channels, active_channels)))

        if sorted(self._active_channels) != sorted(active_channels) or \
                sorted(self._channels) != sorted(channels):
            self._channels = channels
            self._active_channels = active_channels
            self.sig_channels_updated.emit(tuple(channels),
                                           tuple(active_channels))
            self.setup(check_updates=True)

    def update_style_sheet(self, style_sheet=None, extra_dialogs={},
                           palette={}):
        if style_sheet:
            self.style_sheet = style_sheet
            self.table.update_style_palette(palette=palette)
            self.textbox_search.update_style_sheet(style_sheet)
            self.setStyleSheet(style_sheet)

        if extra_dialogs:
            cancel_dialog = extra_dialogs.get('cancel_dialog', None)
            apply_actions_dialog = extra_dialogs.get('apply_actions_dialog',
                                                     None)
            message_box_error = extra_dialogs.get('message_box_error',
                                                  None)
            if cancel_dialog:
                self.cancel_dialog = cancel_dialog
            if apply_actions_dialog:
                self.apply_actions_dialog = apply_actions_dialog
            if message_box_error:
                self.message_box_error = message_box_error

    # --- UI API
    # -------------------------------------------------------------------------
    def filter_package(self, value):
        """ """
        self.table.filter_status_changed(value)

    def show_channels_dialog(self):
        """
        Show the channels dialog.
        """
        button_channels = self.button_channels
        self.dlg = DialogChannels(self,
                                  channels=self._channels,
                                  active_channels=self._active_channels,
                                  conda_url=self.conda_url)
        self.dlg.update_style_sheet(style_sheet=self.style_sheet)
        button_channels.setDisabled(True)
        self.dlg.sig_channels_updated.connect(self.update_channels)
        self.dlg.rejected.connect(lambda: button_channels.setEnabled(True))
        self.dlg.rejected.connect(button_channels.toggle)
        self.dlg.rejected.connect(button_channels.setFocus)
        self.dlg.accepted.connect(self.accept_channels_dialog)

        geo_tl = button_channels.geometry().topLeft()
        tl = button_channels.parentWidget().mapToGlobal(geo_tl)
        x = tl.x() + 2
        y = tl.y() + button_channels.height()
        self.dlg.move(x, y)
        self.dlg.show()
        self.dlg.button_add.setFocus()

    def update_package_index(self):
        """ """
        self.setup(check_updates=True)

    def search_package(self, text):
        """ """
        self.table.search_string_changed(text)

    def apply_multiple_actions(self):
        """
        """
        logger.debug('')

        self.conda_errors = []

        prefix = self.prefix

        if prefix == self.root_prefix:
            name = 'root'
        elif self.api.conda_environment_exists(prefix=prefix):
            name = osp.basename(prefix)
        else:
            name = prefix

        actions = self.table.get_actions()

        if actions is None:
            return

        self._multiple_process = deque()

        pip_actions = actions[C.PIP_PACKAGE]
        conda_actions = actions[C.CONDA_PACKAGE]

        pip_remove = pip_actions.get(C.ACTION_REMOVE, [])
        conda_remove = conda_actions.get(C.ACTION_REMOVE, [])
        conda_install = conda_actions.get(C.ACTION_INSTALL, [])
        conda_upgrade = conda_actions.get(C.ACTION_UPGRADE, [])
        conda_downgrade = conda_actions.get(C.ACTION_DOWNGRADE, [])

        message = ''
        template_1 = '<li><b>{0}={1}</b></li>'
        template_2 = '<li><b>{0}: {1} -> {2}</b></li>'

        if pip_remove:
            temp = [template_1.format(i['name'], i['version_to']) for i in
                    pip_remove]
            message += ('The following pip packages will be removed: '
                        '<ul>' + ''.join(temp) + '</ul>')
        if conda_remove:
            temp = [template_1.format(i['name'], i['version_to']) for i in
                    conda_remove]
            message += ('<br>The following conda packages will be removed: '
                        '<ul>' + ''.join(temp) + '</ul>')
        if conda_install:
            temp = [template_1.format(i['name'], i['version_to']) for i in
                    conda_install]
            message += ('<br>The following conda packages will be installed: '
                        '<ul>' + ''.join(temp) + '</ul>')
        if conda_downgrade:
            temp = [template_2.format(
                    i['name'], i['version_from'], i['version_to']) for i in
                    conda_downgrade]
            message += ('<br>The following conda packages will be downgraded: '
                        '<ul>' + ''.join(temp) + '</ul>')
        if conda_upgrade:
            temp = [template_2.format(
                    i['name'], i['version_from'], i['version_to']) for i in
                    conda_upgrade]
            message += ('<br>The following conda packages will be upgraded: '
                        '<ul>' + ''.join(temp) + '</ul>')
        message += '<br>'

        if self.apply_actions_dialog:
            dlg = self.apply_actions_dialog(message, parent=self)
            dlg.update_style_sheet(style_sheet=self.style_sheet)
            reply = dlg.exec_()
        else:
            reply = QMessageBox.question(self,
                                         'Proceed with the following actions?',
                                         message,
                                         buttons=QMessageBox.Ok |
                                         QMessageBox.Cancel)

        if reply:
            # Pip remove
            for pkg in pip_remove:
                status = (_('Removing pip package <b>') + pkg['name'] +
                          '</b>' + _(' from <i>') + name + '</i>')
                pkgs = [pkg['name']]

                def trigger(prefix=prefix, pkgs=pkgs):
                    return lambda: self.api.pip_remove(prefix=prefix,
                                                       pkgs=pkgs)

                self._multiple_process.append([status, trigger()])

            # Process conda actions
            if conda_remove:
                status = (_('Removing conda packages <b>') +
                          '</b>' + _(' from <i>') + name + '</i>')
                pkgs = [i['name'] for i in conda_remove]

                def trigger(prefix=prefix, pkgs=pkgs):
                    return lambda: self.api.conda_remove(pkgs=pkgs,
                                                         prefix=prefix)
                self._multiple_process.append([status, trigger()])

            if conda_install:
                pkgs = ['{0}={1}'.format(i['name'], i['version_to']) for i in
                        conda_install]

                status = (_('Installing conda packages <b>') +
                          '</b>' + _(' on <i>') + name + '</i>')

                def trigger(prefix=prefix, pkgs=pkgs):
                    return lambda: self.api.conda_install(
                        prefix=prefix,
                        pkgs=pkgs,
                        channels=self._active_channels,
                        token=self.token)
                self._multiple_process.append([status, trigger()])

            # Conda downgrade
            if conda_downgrade:
                status = (_('Downgrading conda packages <b>') +
                          '</b>' + _(' on <i>') + name + '</i>')

                pkgs = ['{0}={1}'.format(i['name'], i['version_to']) for i in
                        conda_downgrade]

                def trigger(prefix=prefix, pkgs=pkgs):
                    return lambda: self.api.conda_install(
                        prefix=prefix,
                        pkgs=pkgs,
                        channels=self._active_channels,
                        token=self.token)

                self._multiple_process.append([status, trigger()])

            # Conda update
            if conda_upgrade:
                status = (_('Upgrading conda packages <b>') +
                          '</b>' + _(' on <i>') + name + '</i>')

                pkgs = ['{0}={1}'.format(i['name'], i['version_to']) for i in
                        conda_upgrade]

                def trigger(prefix=prefix, pkgs=pkgs):
                    return lambda: self.api.conda_install(
                        prefix=prefix,
                        pkgs=pkgs,
                        channels=self._active_channels,
                        token=self.token)

                self._multiple_process.append([status, trigger()])

            self._run_multiple_actions()

    def clear_actions(self):
        """
        """
        self.table.clear_actions()

    def cancel_process(self):
        """
        Allow user to cancel an ongoing process.
        """
        logger.debug(str('process canceled by user.'))
        if self.busy:
            dlg = self.cancel_dialog()
            reply = dlg.exec_()
            if reply:
                self.update_status(hide=False, message='Process cancelled')
                self.api.conda_terminate()
                self.api.download_requests_terminate()
                self.api.conda_clear_lock()
                self.table.clear_actions()
                self.sig_process_cancelled.emit()
        else:
            QDialog.reject(self)

    def update_status(self, message=None, hide=True, progress=None,
                      env=False):
        """
        Update status bar, progress bar display and widget visibility

        message : str
            Message to display in status bar.
        hide : bool
            Enable/Disable widgets.
        progress : [int, int]
            Show status bar progress. [0, 0] means spinning statusbar.
        """
        self.busy = hide
        for widget in self.widgets:
            widget.setDisabled(hide)
        self.table.verticalScrollBar().setValue(self._current_table_scroll)

        self.button_apply.setVisible(False)
        self.button_clear.setVisible(False)

        self.progress_bar.setVisible(hide)
        self.button_cancel.setVisible(hide)

        if message is not None:
            self.message = message

        if self.prefix == self.root_prefix:
            short_env = 'root'
#        elif self.api.environment_exists(prefix=self.prefix):
#            short_env = osp.basename(self.prefix)
        else:
            short_env = self.prefix

        if env:
            self.message = '{0} (<b>{1}</b>)'.format(
                self.message, short_env,
                )
        self.status_bar.setText(self.message)

        if progress is not None:
            current_progress, max_progress = 0, 0

            if progress[1]:
                max_progress = progress[1]

            if progress[0]:
                current_progress = progress[0]

            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(max_progress)
            self.progress_bar.setValue(current_progress)
        else:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(0)

    # --- Conda helpers
    # -------------------------------------------------------------------------
    def get_environment_prefix(self):
        """
        Returns the active environment prefix.
        """
        return self._prefix

    def get_environment_name(self):
        """
        Returns the active environment name if it is located in the default
        conda environments directory, otherwise it returns the prefix.
        """
        name = osp.basename(self._prefix)

        if not (name and self.api.environment_exists(name=name)):
            name = self._prefix

        return name

    def get_environments(self):
        """
        Get a list of conda environments located in the default conda
        environments directory.
        """
        return self.api.conda_get_envs()

    def get_prefix_envname(self, name):
        """
        Returns the prefix for a given environment by name.
        """
        return self.api.conda_get_prefix_envname(name)

    def get_package_versions(self, name):
        """ """
        return self.table.source_model.get_package_versions(name)

    # --- Conda actions
    # -------------------------------------------------------------------------
    def create_environment(self, name=None, prefix=None, packages=['python']):
        """ """
        # If environment exists already? GUI should take care of this
        # BUT the api call should simply set that env as the env
        dic = {}
        dic['name'] = name
        dic['prefix'] = prefix
        dic['pkgs'] = packages
        dic['dep'] = True  # Not really needed but for the moment!
        dic['action'] = C.ACTION_CREATE
        return self._run_conda_process(dic['action'], dic)

    def clone_environment(self, name=None, prefix=None, clone=None):
        dic = {}
        dic['name'] = name
        dic['prefix'] = prefix
        dic['clone'] = clone
        dic['pkgs'] = None
        dic['dep'] = True  # Not really needed but for the moment!
        dic['action'] = C.ACTION_CLONE
        return self._run_conda_process(dic['action'], dic)

    def remove_environment(self, name=None, prefix=None):
        dic = {}
        dic['name'] = name
        dic['pkgs'] = None
        dic['dep'] = True  # Not really needed but for the moment!
        dic['action'] = C.ACTION_REMOVE_ENV
        return self._run_conda_process(dic['action'], dic)


class CondaPackagesDialog(QDialog, CondaPackagesWidget):
    """
    Conda packages dialog.

    Dialog version of the CondaPackagesWidget.
    """
    sig_worker_ready = Signal()
    sig_packages_ready = Signal()
    sig_environment_created = Signal()
    sig_channels_updated = Signal(tuple, tuple)  # channels, active_channels
    sig_next_focus = Signal()
    sig_process_cancelled = Signal()
    sig_packages_busy = Signal()

    def __init__(self,
                 parent=None,
                 name=None,
                 prefix=None,
                 channels=(),
                 active_channels=(),
                 conda_url='https://conda.anaconda.org'):

        super(CondaPackagesDialog, self).__init__(
            parent=parent,
            name=name,
            prefix=prefix,
            channels=channels,
            active_channels=active_channels,
            conda_url=conda_url,
            )

        # Widgets setup
        self.button_ok.setVisible(True)
        self.button_ok.setMaximumSize(self.button_ok.sizeHint())

        # Signals
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
    widget = CondaPackagesWidget(None, prefix='/home/goanpeca/anaconda2')
    widget.show()
    sys.exit(app.exec_())


def test_dialog():
    """Run conda packages widget test"""
    from conda_manager.utils.qthelpers import qapplication
    app = qapplication()
    dialog = CondaPackagesDialog(name='root')
    sys.exit(dialog.exec_())


if __name__ == '__main__':
    test_dialog()
    #test_widget()
