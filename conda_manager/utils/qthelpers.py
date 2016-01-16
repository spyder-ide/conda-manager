# -*- coding: utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
# Copyright © 2012 Pierre Raybaut
#
# Licensed under the terms of the MIT License

"""
Qt utilities.
"""

import os

from qtpy.compat import to_qvariant
from qtpy.QtCore import Qt, QLocale, QTranslator, QLibraryInfo, QTimer
from qtpy.QtWidgets import QAction, QApplication, QMenu, QToolButton


def qapplication(translate=True, test_time=3):
    """Return QApplication instance
    Creates it if it doesn't already exist"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(['Conda-Manager'])
        app.setApplicationName('Conda-Manager')
    if translate:
        install_translator(app)

    test_travis = os.environ.get('TEST_CI', None)
    if test_travis is not None:
        timer_shutdown = QTimer(app)
        timer_shutdown.timeout.connect(app.quit)
        timer_shutdown.start(test_time*1000)
    return app


QT_TRANSLATOR = None


def install_translator(qapp):
    """Install Qt translator to the QApplication instance"""
    global QT_TRANSLATOR
    if QT_TRANSLATOR is None:
        qt_translator = QTranslator()
        if qt_translator.load(
           "qt_"+QLocale.system().name(),
           QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
            QT_TRANSLATOR = qt_translator  # Keep reference alive
    if QT_TRANSLATOR is not None:
        qapp.installTranslator(QT_TRANSLATOR)


def action2button(action, autoraise=True, text_beside_icon=False, parent=None):
    """Create a QToolButton directly from a QAction object"""
    if parent is None:
        parent = action.parent()
    button = QToolButton(parent)
    button.setDefaultAction(action)
    button.setAutoRaise(autoraise)
    if text_beside_icon:
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    return button


def toggle_actions(actions, enable):
    """Enable/disable actions"""
    if actions is not None:
        for action in actions:
            if action is not None:
                action.setEnabled(enable)


def create_action(parent, text, shortcut=None, icon=None, tip=None,
                  toggled=None, triggered=None, data=None, menurole=None,
                  context=Qt.WindowShortcut):
    """Create a QAction"""
    action = QAction(text, parent)
    if triggered is not None:
        action.triggered.connect(triggered)
    if toggled is not None:
        action.toggled.connect(toggled)
        action.setCheckable(True)
    if icon is not None:
        action.setIcon(icon)
    if shortcut is not None:
        action.setShortcut(shortcut)
    if tip is not None:
        action.setToolTip(tip)
        action.setStatusTip(tip)
    if data is not None:
        action.setData(to_qvariant(data))
    if menurole is not None:
        action.setMenuRole(menurole)
    #TODO: Hard-code all shortcuts and choose context=Qt.WidgetShortcut
    # (this will avoid calling shortcuts from another dockwidget
    #  since the context thing doesn't work quite well with these widgets)
    action.setShortcutContext(context)
    return action


def add_actions(target, actions, insert_before=None):
    """Add actions to a menu"""
    previous_action = None
    target_actions = list(target.actions())
    if target_actions:
        previous_action = target_actions[-1]
        if previous_action.isSeparator():
            previous_action = None
    for action in actions:
        if (action is None) and (previous_action is not None):
            if insert_before is None:
                target.addSeparator()
            else:
                target.insertSeparator(insert_before)
        elif isinstance(action, QMenu):
            if insert_before is None:
                target.addMenu(action)
            else:
                target.insertMenu(insert_before, action)
        elif isinstance(action, QAction):
            if insert_before is None:
                target.addAction(action)
            else:
                target.insertAction(insert_before, action)
        previous_action = action
