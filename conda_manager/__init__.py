

__version__ = '0.1.1'


# Constants
COLUMNS = (NAME, DESCRIPTION, VERSION, STATUS, URL, LICENSE, INSTALL,
           REMOVE, UPGRADE, DOWNGRADE, ENDCOL) = list(range(11))
ACTION_COLUMNS = [INSTALL, REMOVE, UPGRADE, DOWNGRADE]
TYPES = (INSTALLED, NOT_INSTALLED, UPGRADABLE, DOWNGRADABLE, ALL_INSTALLABLE,
         ALL, NOT_INSTALLABLE, MIXGRADABLE, CREATE, CLONE,
         REMOVE_ENV) = list(range(11))
COMBOBOX_VALUES_ORDERED = [_(u'Installed'), _(u'Not installed'),
                           _(u'Upgradable'), _(u'Downgradable'),
                           _(u'All instalable'), _(u'All')]
COMBOBOX_VALUES = dict(zip(COMBOBOX_VALUES_ORDERED, TYPES))
HIDE_COLUMNS = [STATUS, URL, LICENSE]
ROOT = 'root'
