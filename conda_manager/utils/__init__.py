# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""

"""

# Standard library imports
import os
import os.path as osp

# Third party imports
from qtpy.QtGui import QIcon

# Local imports
from conda_manager.data.images import IMG_PATH
from conda_manager.data.repodata import REPODATA_PATH
from conda_manager.utils import encoding
from conda_manager.utils.py3compat import is_unicode, u


def get_image_path(filename):
    """ """
    img_path = os.path.join(IMG_PATH, filename)

    if os.path.isfile(img_path):
        return img_path
    else:
        return None


def get_icon(filename):
    """ """
    icon = get_image_path(filename)
    if icon:
        return QIcon(icon)
    else:
        return QIcon()


def get_home_dir():
    """
    Return user home directory
    """
    try:
        # expanduser() returns a raw byte string which needs to be
        # decoded with the codec that the OS is using to represent file paths.
        path = encoding.to_unicode_from_fs(osp.expanduser('~'))
    except:
        path = ''
    for env_var in ('HOME', 'USERPROFILE', 'TMP'):
        if osp.isdir(path):
            break
        # os.environ.get() returns a raw byte string which needs to be
        # decoded with the codec that the OS is using to represent environment
        # variables.
        path = encoding.to_unicode_from_fs(os.environ.get(env_var, ''))
    if path:
        return path
    else:
        raise RuntimeError('Please define environment variable $HOME')


def get_conf_path(filename=None):
    """Return absolute path for configuration file with specified filename."""
    conf_dir = osp.join(get_home_dir(), '.condamanager')

    if not osp.isdir(conf_dir):
        os.mkdir(conf_dir)

    if filename is None:
        return conf_dir
    else:
        return osp.join(conf_dir, filename)


def get_module_data_path():
    """ """
    return REPODATA_PATH


def sort_versions(versions=(), reverse=False, sep=u'.'):
    """Sort a list of version number strings.

    This function ensures that the package sorting based on number name is
    performed correctly when including alpha, dev rc1 etc...
    """
    if versions == []:
        return []

    digits = u'0123456789'

    def toint(x):
        try:
            n = int(x)
        except:
            n = x
        return n
    versions = list(versions)
    new_versions, alpha, sizes = [], set(), set()

    for item in versions:
        it = item.split(sep)
        temp = []
        for i in it:
            x = toint(i)
            if not isinstance(x, int):
                x = u(x)
                middle = x.lstrip(digits).rstrip(digits)
                tail = toint(x.lstrip(digits).replace(middle, u''))
                head = toint(x.rstrip(digits).replace(middle, u''))
                middle = toint(middle)
                res = [head, middle, tail]
                while u'' in res:
                    res.remove(u'')
                for r in res:
                    if is_unicode(r):
                        alpha.add(r)
            else:
                res = [x]
            temp += res
        sizes.add(len(temp))
        new_versions.append(temp)

    # replace letters found by a negative number
    replace_dic = {}
    alpha = sorted(alpha, reverse=True)
    if len(alpha):
        replace_dic = dict(zip(alpha, list(range(-1, -(len(alpha)+1), -1))))

    # Complete with zeros based on longest item and replace alphas with number
    nmax = max(sizes)
    for i in range(len(new_versions)):
        item = []
        for z in new_versions[i]:
            if z in replace_dic:
                item.append(replace_dic[z])
            else:
                item.append(z)

        nzeros = nmax - len(item)
        item += [0]*nzeros
        item += [versions[i]]
        new_versions[i] = item

    new_versions = sorted(new_versions, reverse=reverse)
    return [n[-1] for n in new_versions]
