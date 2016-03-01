# -*- coding: utf-8 -*-

# Standard library imports
import logging.handlers
import os

# Local imports
from conda_manager.utils import get_conf_path


path = get_conf_path()
logfile = os.path.join(path, 'condamanager.log')


def setup():
    logger = logging.getLogger('navigator')
    logger.setLevel(logging.DEBUG)

    ch = logging.handlers.RotatingFileHandler(logfile, maxBytes=2*1024*1024,
                                              backupCount=5)
    ch.setLevel(logging.DEBUG)

    f = ('%(asctime)s - %(levelname)s\n'
         '    %(module)s.%(funcName)s : %(lineno)d\n'
         '    %(message)s\n')
    formatter = logging.Formatter(f)
    ch.setFormatter(formatter)

    logger.addHandler(ch)

    logger.info('Setting up logger')
    return logger

logger = setup()


def logme(func):
    """
    Can use this as a decorator to log all calls to some function

    If used with the standard formatter above, the function name and location
    will always be right here (not very useful).
    """
    def f(*args, **kwargs):
        logger = setup()
        logger.debug(str(args[1:], **kwargs))
        func(*args, **kwargs)
    return f

te = None


def log_popup():
    from qtpy.QtWidgets import QTextEdit
    global te
    if te is None:
        te = QTextEdit(None)
    te.clear()
    te.setText(open(logfile).read())
    te.verticalScrollBar().setValue(te.verticalScrollBar().maximum())
    te.show()

    def key(*args):
        QTextEdit.keyPressEvent(te, *args)
        log_popup()
    te.keyPressEvent = key
