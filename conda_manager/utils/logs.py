# -*- coding: utf-8 -*-

# Standard library imports
import logging.handlers
import os

# Local imports
from conda_manager.utils import get_conf_path


logfolder = os.path.join(get_conf_path(), 'logs')
logfile = os.path.join(logfolder, 'condamanager.log')


def setup():
    if not os.path.isdir(logfolder):
        os.mkdir(logfolder)

    logger = logging.getLogger('condamanager')
    logger.setLevel(logging.DEBUG)

#    ch = logging.handlers.RotatingFileHandler(logfile, maxBytes=2*1024*1024,
#                                              backupCount=5, mode='w')
    ch = logging.FileHandler(logfile, mode='w')
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
