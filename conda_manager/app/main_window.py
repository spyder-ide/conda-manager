from qtpy.qt import QtWidgets, QtCore
from qregexeditor.app.forms import main_window_ui
from qregexeditor.app.settings import Settings
from qregexeditor import __version__


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = main_window_ui.Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('QRegexEditor v.%s' % __version__)
        self._settings = Settings()
        if self._settings.window_geometry:
            self.restoreGeometry(self._settings.window_geometry)
        if self._settings.window_state:
            self.restoreState(self._settings.window_state)
        self.ui.dockWidget.setVisible(self._settings.show_quick_ref)
        self.ui.dockWidget.visibilityChanged.connect(
            self.ui.editor.ui.checkBoxQuickRef.setChecked)
        self.ui.editor.quick_ref_checked = self._settings.show_quick_ref
        self.ui.editor.compile_flags = self._settings.compile_flags
        self.ui.editor.regex = self._settings.regex
        self.ui.editor.string = self._settings.string
        self.ui.editor.quick_ref_requested.connect(
            self.ui.dockWidget.setVisible)

    def closeEvent(self, ev):
        self._settings.window_geometry = self.saveGeometry()
        self._settings.window_state = self.saveState()
        self._settings.show_quick_ref = self.ui.editor.quick_ref_checked
        self._settings.regex = self.ui.editor.regex
        self._settings.compile_flags = self.ui.editor.compile_flags
        self._settings.string = self.ui.editor.string
