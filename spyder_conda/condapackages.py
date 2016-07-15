# -*- coding:utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright © 2015- The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License
# -----------------------------------------------------------------------------
"""Conda Package Manager Plugin."""

# Standard library imports
import gettext
import os.path as osp

# Third party imports
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QGroupBox, QMessageBox, QVBoxLayout
from spyderlib.plugins import SpyderPluginMixin, PluginConfigPage

# Local imports
from conda_manager.api.manager_api import ManagerAPI
from conda_manager.data import images
from conda_manager.widgets.packages import CondaPackagesWidget


_ = gettext.gettext


class CondaPackagesConfigPage(PluginConfigPage):
    """ """
    
    def setup_page(self):
        self.api = ManagerAPI()
        self.set_option('api', self.api.client_get_api_url())
        self.apply_callback = self.apply_setting_options

        group_api = QGroupBox(_("Anaconda client"))
        self.lineedit_api = self.create_lineedit(_('API url'), 'api',
                                                 alignment=Qt.Horizontal)

#        group_network = QGroupBox(_("Network proxy"))
#        checkbox_proxy = self.create_checkbox(_("Use custom proxy"),
#                                              'use_network_proxy',
#                                              default=False)
#        server = self.create_lineedit(_('Server'), 'server', default='',
#                                      alignment=Qt.Horizontal)
#        port = self.create_lineedit(_('Port'), 'port', default='',
#                                    alignment=Qt.Horizontal)
#        user = self.create_lineedit(_('User'), 'user', default='',
#                                    alignment=Qt.Horizontal)
#        password = self.create_lineedit(_('Password'), 'password', default='',
#                                        alignment=Qt.Horizontal)
        
        # Layouts
        layout_api = QVBoxLayout()
        layout_api.addWidget(self.lineedit_api )
        group_api.setLayout(layout_api)

#        layout_proxy = QGridLayout()
#        layout_proxy.addWidget(checkbox_proxy, 0, 0, 1, 2)
#        layout_proxy.addWidget(server.label, 1, 0)
#        layout_proxy.addWidget(server.textbox, 1, 1)
#        layout_proxy.addWidget(port.label, 1, 2)
#        layout_proxy.addWidget(port.textbox, 1, 3)
#        layout_proxy.addWidget(user.label, 2, 0)
#        layout_proxy.addWidget(user.textbox, 2, 1)
#        layout_proxy.addWidget(password.label, 2, 2)
#        layout_proxy.addWidget(password.textbox, 2, 3)
#        group_network.setLayout(layout_proxy)

        vlayout = QVBoxLayout()
        vlayout.addWidget(group_api)
#        vlayout.addWidget(group_network)
        vlayout.addStretch(1)
        self.setLayout(vlayout)
#
#        # Setup
#        checked = self.get_option('use_network_proxy', default=False)
#        checkbox_proxy.toggled.connect(server.textbox.setEnabled)
#        checkbox_proxy.toggled.connect(port.textbox.setEnabled)
#        checkbox_proxy.toggled.connect(user.textbox.setEnabled)
#        checkbox_proxy.toggled.connect(password.textbox.setEnabled)
#        server.textbox.setEnabled(checked)
#        port.textbox.setEnabled(checked)
#        user.textbox.setEnabled(checked)
#        password.textbox.setEnabled(checked)

    def apply_setting_options(self):
        # TODO: Check value is valid. Add this functionality to configdialog
        self.api.client_set_api_url(self.lineedit_api.textbox.text())


class CondaPackages(CondaPackagesWidget, SpyderPluginMixin):
    """Conda package manager based on conda and conda-api."""

    CONF_SECTION = 'conda_manager'
    CONFIGWIDGET_CLASS = CondaPackagesConfigPage

    sig_environment_created = Signal()

    def __init__(self, parent=None):
        channels = self.get_option('channels', ['anaconda', 'spyder-ide'])
        active_channels = self.get_option('active_channels',
                                          ['anaconda', 'spyder-ide'])
        CondaPackagesWidget.__init__(self,
                                     parent=parent,
                                     channels=channels,
                                     active_channels=active_channels,
                                     )
        SpyderPluginMixin.__init__(self, parent)

        self.root_env = 'root'
        self._prefix_to_set = self.get_environment_prefix()

        # Initialize plugin
        self.initialize_plugin()

    # ------ SpyderPluginWidget API -------------------------------------------
    def get_plugin_title(self):
        """Return widget title"""
        return _("Conda manager")

    def get_plugin_icon(self):
        """Return widget icon"""
        return QIcon(images.PATH_CONDA_LOGO)        

    def get_focus_widget(self):
        """
        Return the widget to give focus to when
        this plugin's dockwidget is raised on top-level
        """
        return self.textbox_search

    def get_plugin_actions(self):
        """Return a list of actions related to plugin"""
        return []

    def on_first_registration(self):
        """Action to be performed on first plugin registration"""
        self.main.tabify_plugins(self.main.help, self)
        self.dockwidget.hide()

    def register_plugin(self):
        """Register plugin in Spyder's main window"""
        main = self.main
        main.add_dockwidget(self)

        #if getattr(main.projectexplorer, 'sig_project_closed', False):
        #    pe = main.projectexplorer
        #    pe.condamanager = self
        #    pe.sig_project_closed.connect(self.project_closed)
        #    pe.sig_project_loaded.connect(self.project_loaded)
        #    self.sig_worker_ready.connect(self._after_load)
        #    self.sig_environment_created.connect(pe.sig_environment_created)

        self.sig_channels_updated.connect(self._save_channel_settings)

    def refresh_plugin(self):
        """Refresh pylint widget"""
        pass

    def closing_plugin(self, cancelable=False):
        """Perform actions before parent main window is closed."""
        if self.busy:
            answer = QMessageBox.question(
                self,
                'Conda Manager',
                'Conda Manager is still busy.\n\nDo you want to quit?',
                buttons=QMessageBox.Yes | QMessageBox.No)

            if answer == QMessageBox.Yes:
                return True
            else:
                return False
        else:
            return True

    def apply_plugin_settings(self, options):
        """Apply configuration file's plugin settings"""
        pass

    # --- Private API ---
    # ----
    def _save_channel_settings(self, channels, active_channels):
        self.set_option('active_channels', active_channels)
        self.set_option('channels', channels)

    # ------ Public API -------------------------------------------------------
    def create_env(self, name, package):
        self.create_environment(name, package)
        if self.dockwidget.isHidden():
            self.dockwidget.show()
        self.dockwidget.raise_()

    def set_env(self, env):
        """ """
#        self.sig_packages_ready.disconnect()
        self.set_environment(env)
        # TODO:

    # ------ Project explorer API ---------------------------------------------
    def get_active_project_path(self):
        """ """
        pe = self.main.projectexplorer
        if pe:
            project = pe.get_active_project()
            if project:
                return project.get_root()

    def project_closed(self, project_path):
        """ """
        self.set_env(self.root_env)

    def project_loaded(self, project_path):
        """ """
        name = osp.basename(project_path)
        

        #self.sig_packages_ready.connect(self.set_env)

        #print('name, envprefix', name, env_prefix)
        # If None, no matching package was found!

        if env:
            self._prefix_to_set = self.get_environment_prefix()
            self.set_env(env)

    def _after_load(self):
        """ """
        active_prefix = self.get_environment_prefix()
        #if active_prefix == 'root':  # Root
        #    self.disable_widgets()
        #else:
        #    self.enable_widgets()


# =============================================================================
# The following statements are required to register this 3rd party plugin:
# =============================================================================
# Only register plugin if conda is found on the system
PLUGIN_CLASS = CondaPackages
