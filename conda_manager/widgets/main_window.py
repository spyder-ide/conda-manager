# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""
Main window.
"""

# Standard library imports
import gettext

# Third party imports
from qtpy.QtCore import QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import QMainWindow, QMenu, QMessageBox

# Local imports
from conda_manager._version import __version__
from conda_manager.utils import get_icon
from conda_manager.utils.py3compat import PY3
from conda_manager.utils.qthelpers import add_actions, create_action
from conda_manager.widgets.packages import CondaPackagesWidget

_ = gettext.gettext


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Variables
        self.file_menu = None
        self.file_menu_actions = []
        self.tools_menu = None
        self.tools_menu_actions = []
        self.help_menu = None
        self.help_menu_actions = []
        self.menulist = []

        # Widgets
        self.packages = CondaPackagesWidget(self)

        # Widget setup
        self.setWindowTitle('Conda Package Manager {0}'.format(__version__))
        self.setCentralWidget(self.packages)

        self.setup_window()

    def setup_window(self):
        """ """
        self.close_action = create_action(self, _("&Quit"),
                                          triggered=self.close)
        self.file_menu_actions.append(self.close_action)
        self.file_menu = self.menuBar().addMenu(_("&File"))
        add_actions(self.file_menu, self.file_menu_actions)

        # Environments
        self.add_env_action = create_action(self, _("&Add"),
                                            triggered=self.add_env)
        self.clone_env_action = create_action(self, _("&Clone"),
                                              triggered=self.clone_env)
        self.remove_env_action = create_action(self, _("&Remove"),
                                               triggered=self.remove_env)
        self.envs_list_menu = QMenu(_('Environments'))
        self.envs_menu_actions = [self.add_env_action, self.clone_env_action,
                                  self.remove_env_action, None,
                                  self.envs_list_menu]
        self.envs_menu = self.menuBar().addMenu(_("&Environments"))
        add_actions(self.envs_menu, self.envs_menu_actions)
        self.update_env_menu()

        # Channels
        self.envs_menu = self.menuBar().addMenu(_("&Channels"))

        # Tools
        self.preferences_action = create_action(self,
                                                _("&Preferences"),
                                                triggered=self.preferences)
        self.tools_menu_actions.append(self.preferences_action)
        self.tools_menu = self.menuBar().addMenu(_("&Tools"))
        add_actions(self.tools_menu, self.tools_menu_actions)

        # Help
        self.report_action = create_action(self,
                                           _("&Report issue"),
                                           triggered=self.report_issue)
        self.about_action = create_action(self, _("&About"),
                                          triggered=self.about)
        self.help_menu_actions.append(self.report_action)
        self.help_menu_actions.append(self.about_action)
        self.help_menu = self.menuBar().addMenu(_("&Help"))
        add_actions(self.help_menu, self.help_menu_actions)

        self.setWindowIcon(get_icon('condapackages.png'))

    def update_env_menu(self):
        """ """
        envs_list_actions = []
        envs = self.get_enviroments()
        self.envs_list_menu.clear()
        for env in envs:
            def trigger(value=False, e=env):
                return lambda: self.set_environments(e)
            a = create_action(self, env, triggered=trigger())
            envs_list_actions.append(a)
        add_actions(self.envs_list_menu, envs_list_actions)

    def get_enviroments(self, path=None):
        """ """
        return ['root'] + self.packages.get_environments()

    def set_environments(self, prefix):
        """ """
        self.packages.set_environment(prefix=prefix)

    def add_env(self):
        """ """
        # TODO:

    def clone_env(self):
        """ """
        # TODO:

    def remove_env(self):
        """ """
        # TODO:

    def preferences(self):
        """ """
        # TODO:

    def report_issue(self):
        if PY3:
            from urllib.parse import quote
        else:
            from urllib import quote     # analysis:ignore

        issue_template = """\
## Description

- *What steps will reproduce the problem?*
1.
2.
3.

- *What is the expected output? What do you see instead?*


- *Please provide any additional information below*


## Version and main components

- Conda Package Manager Version:  {version}
- Conda Version:  {conda version}
- Python Version:  {python version}
- Qt Version    :  {Qt version}
- QtPy Version    :  {QtPy version}
"""
        url = QUrl("https://github.com/spyder-ide/conda-manager/issues/new")
        url.addEncodedQueryItem("body", quote(issue_template))
        QDesktopServices.openUrl(url)

    def about(self):
        """About Conda Package Manager."""
        var = {'github': 'https://github.com/spyder-ide/conda-manager'}

        QMessageBox.about(self, _("About"), """
            <p><b>Conda Package Manager</b></p>

            <p>Copyright &copy; 2015 The Spyder Development Team<br>
            Licensed under the terms of the MIT License</p>

            <p>Created by Gonzalo Pe&ntilde;a-Castellanos<br>
            Developed and maintained by the Spyder Development Team.</p>

            <p>For bug reports and feature requests, please go
            to our <a href="{github}">Github website</a>.</p>

            <p>This project is part of a larger effort to promote and
            facilitate the use of Python for scientific and engineering
            software development. The popular Python distributions
            <a href="http://continuum.io/downloads">Anaconda</a>,
            <a href="https://winpython.github.io/">WinPython</a> and
            <a href="http://code.google.com/p/pythonxy/">Python(x,y)</a>
            also contribute to this plan.</p>
            """.format(**var))

    def closeEvent(self, event):
        """ """
        if self.packages.busy:
            answer = QMessageBox.question(
                self,
                'Quit Conda Manager?',
                'Conda is still busy.\n\nDo you want to quit?',
                buttons=QMessageBox.Yes | QMessageBox.No)

            if answer == QMessageBox.Yes:
                QMainWindow.closeEvent(self, event)
                # Do some cleanup?
            else:
                event.ignore()
        else:
            QMainWindow.closeEvent(self, event)
