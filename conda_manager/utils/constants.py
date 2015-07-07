# -*- coding: utf-8 -*-
"""

"""

import gettext


_ = gettext.gettext


# Constants
COLUMNS = (NAME, DESCRIPTION, VERSION, STATUS, URL, LICENSE, INSTALL,
           REMOVE, UPGRADE, DOWNGRADE, ENDCOL, CREATE, CLONE,
           REMOVE_ENV) = list(range(14))
ACTION_COLUMNS = [INSTALL, REMOVE, UPGRADE, DOWNGRADE]
TYPES = (INSTALLED, NOT_INSTALLED, UPGRADABLE, DOWNGRADABLE, ALL_INSTALLABLE,
         ALL, NOT_INSTALLABLE, MIXGRADABLE) = list(range(8))
COMBOBOX_VALUES_ORDERED = [_(u'Installed'), _(u'Not installed'),
                           _(u'Upgradable'), _(u'Downgradable'),
                           _(u'All installable'), _(u'All')]
COMBOBOX_VALUES = dict(zip(COMBOBOX_VALUES_ORDERED, TYPES))
ROOT = 'root'
