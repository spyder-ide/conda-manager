# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""

"""

# Standard library imports
import gettext


_ = gettext.gettext


# Constants
COLUMNS = (PACKAGE_TYPE, NAME, DESCRIPTION, VERSION, STATUS, URL, LICENSE,
           INSTALL, REMOVE, UPGRADE, DOWNGRADE, ENDCOL) = list(range(0, 12))
ACTION_COLUMNS = [INSTALL, REMOVE, UPGRADE, DOWNGRADE]
PACKAGE_TYPES = (CONDA, PIP) = ['     conda', '    pip']
PACKAGE_STATUS = (INSTALLED, NOT_INSTALLED, UPGRADABLE, DOWNGRADABLE,
                  ALL_INSTALLABLE, ALL, NOT_INSTALLABLE,
                  MIXGRADABLE) = list(range(200, 208))
COMBOBOX_VALUES_ORDERED = [_(u'Installed'), _(u'Not installed'),
                           _(u'Upgradable'), _(u'Downgradable'),
                           _(u'All installable'), _(u'All')]
COMBOBOX_VALUES = dict(zip(COMBOBOX_VALUES_ORDERED, PACKAGE_STATUS))
ROOT = 'root'
