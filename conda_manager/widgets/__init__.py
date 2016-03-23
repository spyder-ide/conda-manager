# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""

"""

# Third party imports
from qtpy.QtWidgets import QComboBox, QFrame, QLabel, QPushButton, QProgressBar


# --- Widgets used in CSS styling
class ButtonBase(QPushButton):
    def __init__(self, *args, **kwargs):
        super(ButtonBase, self).__init__(*args, **kwargs)
        self.setDefault(True)


class ButtonPackageCancel(ButtonBase):
    pass


class ButtonPackageChannels(ButtonBase):
    pass


class ButtonPackageOk(ButtonBase):
    pass


class ButtonPackageUpdate(ButtonBase):
    pass


class ButtonPackageApply(ButtonBase):
    pass


class ButtonPackageClear(ButtonBase):
    pass


# Channel dialog widgets
class ButtonPackageChannelAdd(ButtonBase):
    pass


class ButtonPackageChannelRemove(ButtonBase):
    pass


class ButtonPackageChannelUpdate(ButtonBase):
    pass


class DropdownPackageFilter(QComboBox):
    pass


class ProgressBarPackage(QProgressBar):
    pass


class LabelPackageStatus(QLabel):
    pass


class FramePackageTop(QFrame):
    pass


class FramePackageBottom(QFrame):
    pass
