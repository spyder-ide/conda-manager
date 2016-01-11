# -*- coding: utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""
Conda Process based on conda-api and QProcess.
"""

# Standard library imports
from os.path import basename, isdir, join
import json
import os
import random
import re
import sys

# Third party imports
from qtpy.QtWidgets import (QApplication, QHBoxLayout, QPushButton,
                            QVBoxLayout, QWidget)
from qtpy.QtCore import QByteArray, QObject, QProcess, Signal


__version__ = '1.2.1'


def symlink_ms(source, link_name):
    """
    http://stackoverflow.com/questions/6260149/os-symlink-support-in-windows
    """
    import ctypes
    csl = ctypes.windll.kernel32.CreateSymbolicLinkW
    csl.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    csl.restype = ctypes.c_ubyte
    flags = 1 if os.path.isdir(source) else 0

    try:
        if csl(link_name, source.replace('/', '\\'), flags) == 0:
            raise ctypes.WinError()
    except:
        pass

if os.name == "nt":
    os.symlink = symlink_ms


# -----------------------------------------------------------------------------
# --- Globals
# -----------------------------------------------------------------------------
PY2 = sys.version[0] == '2'
PY3 = sys.version[0] == '3'


# -----------------------------------------------------------------------------
# --- Utils
# -----------------------------------------------------------------------------
def to_text_string(obj, encoding=None):
    """Convert `obj` to (unicode) text string"""
    if PY2:
        # Python 2
        if encoding is None:
            return unicode(obj)
        else:
            return unicode(obj, encoding)
    else:
        # Python 3
        if encoding is None:
            return str(obj)
        elif isinstance(obj, str):
            # In case this function is not used properly, this could happen
            return obj
        else:
            return str(obj, encoding)


def handle_qbytearray(obj, encoding):
    """ """
    if isinstance(obj, QByteArray):
        obj = obj.data()

    return to_text_string(obj, encoding=encoding)


# -----------------------------------------------------------------------------
# --- Errors
# -----------------------------------------------------------------------------
class CondaError(Exception):
    """General Conda error."""
    pass


class CondaEnvExistsError(CondaError):
    """Conda environment already exists."""
    pass


# -----------------------------------------------------------------------------
# --- Conda API Qt
# -----------------------------------------------------------------------------
class CondaProcess(QObject):
    """Conda API modified to work with QProcess instead of popen."""

    # Signals
    sig_finished = Signal(str, object, str)
    sig_partial = Signal(str, object, str)
    sig_started = Signal()

    ENCODING = 'ascii'
    ROOT_PREFIX = None

    def __init__(self, parent):
        QObject.__init__(self, parent)
        self._parent = parent
        self._output = None
        self._partial = None
        self._stdout = None
        self._error = None
        self._parse = False
        self._function_called = ''
        self._name = None
        self._process = QProcess()
        self.set_root_prefix()

        # Signals
        self._process.finished.connect(self._call_conda_ready)
        self._process.readyReadStandardOutput.connect(self._call_conda_partial)

    # --- Helpers
    # -------------------------------------------------------------------------
    def _is_running(self):
        return self._process.state() != QProcess.NotRunning

    def _is_not_running(self):
        return self._process.state() == QProcess.NotRunning

    def _call_conda_partial(self):
        """ """
        stdout = self._process.readAllStandardOutput()
        stdout = handle_qbytearray(stdout, CondaProcess.ENCODING)

        stderr = self._process.readAllStandardError()
        stderr = handle_qbytearray(stderr, CondaProcess.ENCODING)

        if self._parse:
            try:
                self._output = json.loads(stdout)
            except Exception:
                # Result is a partial json. Can only be parsed when finished
                self._output = stdout
        else:
            self._output = stdout

        self._partial = self._output
        self._stdout = self._output
        self._error = stderr

        self.sig_partial.emit(self._function_called, self._partial,
                              self._error)

    def _call_conda_ready(self):
        """Function called when QProcess in _call_conda finishes task."""
        function = self._function_called

        if self._stdout is None:
            stdout = to_text_string(self._process.readAllStandardOutput(),
                                    encoding=CondaProcess.ENCODING)
        else:
            stdout = self._stdout

        if self._error is None:
            stderr = to_text_string(self._process.readAllStandardError(),
                                    encoding=CondaProcess.ENCODING)
        else:
            stderr = self._error

        if function == 'get_conda_version':
            pat = re.compile(r'conda:?\s+(\d+\.\d\S+|unknown)')
            m = pat.match(stderr.strip())
            if m is None:
                m = pat.match(stdout.strip())
            if m is None:
                raise Exception('output did not match: {0}'.format(stderr))
            self._output = m.group(1)
        elif function == 'config_path':
            result = self._output
            self._output = result['rc_path']
        elif function == 'config_get':
            result = self._output
            self._output = result['get']
        elif (function == 'config_delete' or function == 'config_add' or
              function == 'config_set' or function == 'config_remove'):
            result = self._output
            self._output = result.get('warnings', [])
        elif function == 'pip':
            result = []
            lines = self._output.split('\n')
            for line in lines:
                if '<pip>' in line:
                    temp = line.split()[:-1] + ['pip']
                    result.append('-'.join(temp))
            self._output = result

        if stderr.strip():
            self._error = stderr

        self._parse = False

        self.sig_finished.emit(self._function_called, self._output,
                               self._error)

    def _abspath(self, abspath):
        """ """
        if abspath:
            if sys.platform == 'win32':
                python = join(CondaProcess.ROOT_PREFIX, 'python.exe')
                conda = join(CondaProcess.ROOT_PREFIX,
                             'Scripts', 'conda-script.py')
            else:
                python = join(CondaProcess.ROOT_PREFIX, 'bin/python')
                conda = join(CondaProcess.ROOT_PREFIX, 'bin/conda')
            cmd_list = [python, conda]
        else:
            # Just use whatever conda/pip is on the path
            cmd_list = ['conda']

        return cmd_list

    def _call_conda(self, extra_args, abspath=True):
        """ """
        if self._is_not_running():
            cmd_list = self._abspath(abspath)
            cmd_list.extend(extra_args)
            self._error, self._output = None, None
            self._process.start(cmd_list[0], cmd_list[1:])
            self.sig_started.emit()

    def _call_pip(self, name=None, prefix=None, extra_args=None):
        """ """
        if self._is_not_running():
            cmd_list = self._pip_cmd(name=name, prefix=prefix)
            cmd_list.extend(extra_args)
            self._error, self._output = None, None
            self._parse = False
            self._process.start(cmd_list[0], cmd_list[1:])
            self.sig_started.emit()

    def _call_and_parse(self, extra_args, abspath=True):
        """ """
        self._parse = True
        self._call_conda(extra_args, abspath=abspath)

    def _setup_install_commands_from_kwargs(self, kwargs, keys=tuple()):
        """ """
        cmd_list = []
        if kwargs.get('override_channels', False) and 'channel' not in kwargs:
            raise TypeError('conda search: override_channels requires channel')

        if 'env' in kwargs:
            cmd_list.extend(['--name', kwargs.pop('env')])
        if 'prefix' in kwargs:
            cmd_list.extend(['--prefix', kwargs.pop('prefix')])
        if 'channel' in kwargs:
            channel = kwargs.pop('channel')
            if isinstance(channel, str):
                cmd_list.extend(['--channel', channel])
            else:
                cmd_list.append('--channel')
                cmd_list.extend(channel)

        for key in keys:
            if key in kwargs and kwargs[key]:
                cmd_list.append('--' + key.replace('_', '-'))

        return cmd_list

    # --- Public api
    # ------------------------------------------------------------------------
    @staticmethod
    def linked(prefix, as_spec=False):
        """
        Return the (set of canonical names) of linked packages in `prefix`.
        """
        if not isdir(prefix):
            raise Exception('no such directory: {0}'.format(prefix))

        meta_dir = join(prefix, 'conda-meta')

        if not isdir(meta_dir):
            # We might have nothing in linked (and no conda-meta directory)
            result = set()

        result = set(fn[:-5] for fn in os.listdir(meta_dir)
                     if fn.endswith('.json'))

        new_result = []
        if as_spec:
            for r in result:
                n, v, b = CondaProcess.split_canonical_name(r)
                new_result.append("{0}={1}".format(n, v))
            result = "\n".join(new_result)

        return result

    @staticmethod
    def split_canonical_name(cname):
        """
        Split a canonical package name into (name, version, build) strings.
        """
        result = tuple(cname.rsplit('-', 2))
        return result

    def set_root_prefix(self, prefix=None):
        """
        Set the prefix to the root environment (default is /opt/anaconda).
        """
        if prefix:
            CondaProcess.ROOT_PREFIX = prefix
        else:
            # Find conda instance, and then use info() to get 'root_prefix'
            if CondaProcess.ROOT_PREFIX is None:
                info = self.info(abspath=False)
                CondaProcess.ROOT_PREFIX = info['root_prefix']

    def get_conda_version(self):
        """
        Return the version of conda being used (invoked) as a string.
        """
        if self._is_not_running():
            self._function_called = 'get_conda_version'
            self._call_conda(['--version'])

    def get_envs(self, emit=False):
        """
        Return all of the (named) environments (this does not include the root
        environment), as a list of absolute paths to their prefixes.
        """
        if self._is_not_running():
            info = self.info()
            result = info['envs']

            if emit:
                self.sig_finished.emit('get_envs', result, "")

            return result

    def get_prefix_envname(self, name, emit=False):
        """
        Given the name of an environment return its full prefix path, or None
        if it cannot be found.
        """
        if self._is_not_running():
            if name == 'root':
                prefix = CondaProcess.ROOT_PREFIX
            for env_prefix in self.get_envs():
                if basename(env_prefix) == name:
                    prefix = env_prefix
                    break
            if emit:
                self.sig_finished.emit('get_prefix_envname', prefix, "")

            return prefix

    def info(self, abspath=True, emit=False):
        """
        Return a dictionary with configuration information.

        No guarantee is made about which keys exist.  Therefore this function
        should only be used for testing and debugging.
        """
        if self._is_not_running():
            qprocess = QProcess()
            cmd_list = self._abspath(abspath)
            cmd_list.extend(['info', '--json'])
            qprocess.start(cmd_list[0], cmd_list[1:])
            qprocess.waitForFinished()
            output = qprocess.readAllStandardOutput()
            output = handle_qbytearray(output, CondaProcess.ENCODING)
            info = json.loads(output)

            if emit:
                self.sig_finished.emit("info", str(info), "")

            return info

    def package_info(self, package, abspath=True):
        """
        Return a dictionary with package information.

        Structure is {
            'package_name': [{
                'depends': list,
                'version': str,
                'name': str,
                'license': str,
                'fn': ...,
                ...
            }]
        }
        """
        if self._is_not_running():
            self._function_called = 'package_info'
            self._call_and_parse(['info', package, '--json'], abspath=abspath)

    def search(self, regex=None, spec=None, **kwargs):
        """
        Search for packages.
        """
        cmd_list = ['search', '--json']

        if regex and spec:
            raise TypeError('conda search: only one of regex or spec allowed')

        if regex:
            cmd_list.append(regex)

        if spec:
            cmd_list.extend(['--spec', spec])

        if 'platform' in kwargs:
            platform = kwargs.pop('platform')
            platforms = ('win-32', 'win-64', 'osx-64', 'linux-32', 'linux-64')
            if platform not in platforms:
                raise TypeError('conda search: platform must be one of ' +
                                ', '.join(platforms))
            cmd_list.extend(['--platform', platform])

        cmd_list.extend(
            self._setup_install_commands_from_kwargs(
                kwargs,
                ('canonical', 'unknown', 'use_index_cache', 'outdated',
                 'override_channels')))

        if self._is_not_running():
            self._function_called = 'search'
            self._call_and_parse(cmd_list, abspath=kwargs.get('abspath', True))

    def share(self, prefix):
        """
        Create a "share package" of the environment located in `prefix`,
        and return a dictionary with (at least) the following keys:
          - 'prefix': the full path to the created package
          - 'warnings': a list of warnings

        This file is created in a temp directory, and it is the callers
        responsibility to remove this directory (after the file has been
        handled in some way).
        """
        if self._is_not_running:
            self._function_called = 'share'
            self._call_and_parse(['share', '--json', '--prefix', prefix])

    def create(self, name=None, prefix=None, pkgs=None):
        """
        Create an environment either by 'name' or 'prefix' with a specified set
        of packages.
        """
        # TODO: Fix temporal hack
        if not pkgs or not isinstance(pkgs, (list, tuple, str)):
            raise TypeError('must specify a list of one or more packages to '
                            'install into new environment')

        cmd_list = ['create', '--yes', '--quiet', '--json', '--mkdir']
        if name:
            ref = name
            search = [os.path.join(d, name) for d in self.info()['envs_dirs']]
            cmd_list.extend(['--name', name])
        elif prefix:
            ref = prefix
            search = [prefix]
            cmd_list.extend(['--prefix', prefix])
        else:
            raise TypeError("Must specify either an environment 'name' or a "
                            "'prefix' for new environment.")

        if any(os.path.exists(path) for path in search):
            raise CondaEnvExistsError('Conda environment [%s] already exists'
                                      % ref)

        # TODO: Fix temporal hack
        if isinstance(pkgs, (list, tuple)):
            cmd_list.extend(pkgs)
        elif isinstance(pkgs, str):
            cmd_list.extend(['--file', pkgs])

        if self._is_not_running:
            self._function_called = 'create'
            self._call_conda(cmd_list)

    def install(self, name=None, prefix=None, pkgs=None, dep=True):
        """
        Install packages into an environment either by 'name' or 'prefix' with
        a specified set of packages
        """        
        # TODO: Fix temporal hack
        if not pkgs or not isinstance(pkgs, (list, tuple, str)):
            raise TypeError('must specify a list of one or more packages to '
                            'install into existing environment')

        cmd_list = ['install', '--yes', '--json', '--force-pscheck']
        if name:
            cmd_list.extend(['--name', name])
        elif prefix:
            cmd_list.extend(['--prefix', prefix])
        else:  # just install into the current environment, whatever that is
            pass

        # TODO: Fix temporal hack
        if isinstance(pkgs, (list, tuple)):
            cmd_list.extend(pkgs)
        elif isinstance(pkgs, str):
            cmd_list.extend(['--file', pkgs])

        if not dep:
            cmd_list.extend(['--no-deps'])

        if self._is_not_running:
            self._function_called = 'install'
            self._call_conda(cmd_list)

    def update(self, *pkgs, **kwargs):
        """
        Update package(s) (in an environment) by name.
        """
        cmd_list = ['update', '--json', '--quiet', '--yes']

        if not pkgs and not kwargs.get('all'):
            raise TypeError("Must specify at least one package to update, \
                            or all=True.")

        cmd_list.extend(
            self._setup_install_commands_from_kwargs(
                kwargs,
                ('dry_run', 'no_deps', 'override_channels',
                 'no_pin', 'force', 'all', 'use_index_cache', 'use_local',
                 'alt_hint')))

        cmd_list.extend(pkgs)

        if self._is_not_running:
            self._function_called = 'update'
            self._call_and_parse(cmd_list, abspath=kwargs.get('abspath', True))

    def remove(self, *pkgs, **kwargs):
        """
        Remove a package (from an environment) by name.

        Returns {
            success: bool, (this is always true),
            (other information)
        }
        """
        cmd_list = ['remove', '--json', '--quiet', '--yes', '--force-pscheck']

        if not pkgs and not kwargs.get('all'):
            raise TypeError("Must specify at least one package to remove, \
                            or all=True.")

        if kwargs.get('name') and kwargs.get('prefix'):
            raise TypeError("conda remove: At most one of 'name', 'prefix' "
                            "allowed")

        if kwargs.get('name'):
            cmd_list.extend(['--name', kwargs.pop('name')])

        if kwargs.get('prefix'):
            cmd_list.extend(['--prefix', kwargs.pop('prefix')])

        cmd_list.extend(
            self._setup_install_commands_from_kwargs(
                kwargs,
                ('dry_run', 'features', 'override_channels',
                 'no_pin', 'force', 'all')))

        cmd_list.extend(pkgs)

        if self._is_not_running:
            self._function_called = 'remove'
            self._call_and_parse(cmd_list,
                                 abspath=kwargs.get('abspath', True))

    def remove_environment(self, name=None, prefix=None, **kwargs):
        """
        Remove an environment entirely.

        See ``remove``.
        """
        if self._is_not_running:
            self._function_called = 'remove_environment'
            self.remove(name=name, prefix=prefix, all=True, **kwargs)

    def clone_environment(self, clone, name=None, prefix=None, **kwargs):
        """
        Clone the environment ``clone`` into ``name`` or ``prefix``.
        """
        cmd_list = ['create', '--json', '--quiet']

        if (name and prefix) or not (name or prefix):
            raise TypeError("conda clone_environment: exactly one of 'name' "
                            "or 'prefix' required.")

        if name:
            cmd_list.extend(['--name', name])

        if prefix:
            cmd_list.extend(['--prefix', prefix])

        cmd_list.extend(['--clone', clone])

        cmd_list.extend(
            self._setup_install_commands_from_kwargs(
                kwargs,
                ('dry_run', 'unknown', 'use_index_cache', 'use_local',
                 'no_pin', 'force', 'all', 'channel', 'override_channels',
                 'no_default_packages')))

        if self._is_not_running():
            self._function_called = 'clone_environment'
            self._call_and_parse(cmd_list, abspath=kwargs.get('abspath', True))

    def clone(self, path, prefix):
        """
        Clone a "share package" (located at `path`) by creating a new
        environment at `prefix`, and return a dictionary with (at least) the
        following keys:
          - 'warnings': a list of warnings

        The directory `path` is located in, should be some temp directory or
        some other directory OUTSIDE /opt/anaconda.  After calling this
        function, the original file (at `path`) may be removed (by the caller
        of this function).
        The return object is a list of warnings.
        """
        if self._process.state() == QProcess.NotRunning:
            self._function_called = 'clone'
            self._call_and_parse(['clone', '--json', '--prefix', prefix, path])

    def _setup_config_from_kwargs(kwargs):
        cmd_list = ['--json', '--force']

        if 'file' in kwargs:
            cmd_list.extend(['--file', kwargs['file']])

        if 'system' in kwargs:
            cmd_list.append('--system')

        return cmd_list

    def config_path(self, **kwargs):
        """
        Get the path to the config file.
        """
        cmd_list = ['config', '--get']
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        if self._is_not_running:
            self._function_called = 'config_path'
            self._call_and_parse(cmd_list, abspath=kwargs.get('abspath', True))

    def config_get(self, *keys, **kwargs):
        """
        Get the values of configuration keys.

        Returns a dictionary of values. Note, the key may not be in the
        dictionary if the key wasn't set in the configuration file.
        """
        cmd_list = ['config', '--get']
        cmd_list.extend(keys)
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        if self._is_not_running:
            self._function_called = 'config_get'
            self._call_and_parse(cmd_list, abspath=kwargs.get('abspath', True))

    def config_set(self, key, value, **kwargs):
        """
        Set a key to a (bool) value.

        Returns a list of warnings Conda may have emitted.
        """
        cmd_list = ['config', '--set', key, str(value)]
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        if self._is_not_running:
            self._function_called = 'config_set'
            self._call_and_parse(cmd_list, abspath=kwargs.get('abspath', True))

    def config_add(self, key, value, **kwargs):
        """
        Add a value to a key.

        Returns a list of warnings Conda may have emitted.
        """
        cmd_list = ['config', '--add', key, value]
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        if self._is_not_running:
            self._function_called = 'config_add'
            self._call_and_parse(cmd_list, abspath=kwargs.get('abspath', True))

    def config_remove(self, key, value, **kwargs):
        """
        Remove a value from a key.

        Returns a list of warnings Conda may have emitted.
        """
        cmd_list = ['config', '--remove', key, value]
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        if self._is_not_running:
            self._function_called = 'config_remove'
            self._call_and_parse(cmd_list, abspath=kwargs.get('abspath', True))

    def config_delete(self, key, **kwargs):
        """
        Remove a key entirely.

        Returns a list of warnings Conda may have emitted.
        """
        cmd_list = ['config', '--remove-key', key]
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        if self._is_not_running:
            self._function_called = 'config_delete'
            self._call_and_parse(cmd_list, abspath=kwargs.get('abspath', True))

    def run(self, command, abspath=True):
        """
        Launch the specified app by name or full package name.

        Returns a dictionary containing the key "fn", whose value is the full
        package (ending in ``.tar.bz2``) of the app.
        """
        cmd_list = ['run', '--json', command]

        if self._is_not_running:
            self._function_called = 'run'
            self._call_and_parse(cmd_list, abspath=abspath)

    # --- Additional methods not in conda-api
    # ------------------------------------------------------------------------
    def dependencies(self, name=None, prefix=None, pkgs=None, dep=True):
        """
        Get dependenciy list for packages to be installed into an environment
        defined either by 'name' or 'prefix'.
        """
        if not pkgs or not isinstance(pkgs, (list, tuple)):
            raise TypeError('must specify a list of one or more packages to '
                            'install into existing environment')

        cmd_list = ['install', '--dry-run', '--json']
        cmd_list = ['install', '--dry-run', '--json', '--force-pscheck']

        if not dep:
            cmd_list.extend(['--no-deps'])

        if name:
            cmd_list.extend(['--name', name])
        elif prefix:
            cmd_list.extend(['--prefix', prefix])
        else:
            pass

        cmd_list.extend(pkgs)

        if self._is_not_running:
            self._function_called = 'install_dry'
            self._call_and_parse(cmd_list)

    def environment_exists(self, name=None, prefix=None, abspath=True,
                           emit=False):
        """
        Check if an environment exists by 'name' or by 'prefix'. If query is
        by 'name' only the default conda environments directory is searched.
        """
        if name and prefix:
            raise TypeError("Exactly one of 'name' or 'prefix' is required.")

        qprocess = QProcess()
        cmd_list = self._abspath(abspath)
        cmd_list.extend(['list', '--json'])

        if name:
            cmd_list.extend(['--name', name])
        else:
            cmd_list.extend(['--prefix', prefix])

        qprocess.start(cmd_list[0], cmd_list[1:])
        qprocess.waitForFinished()
        output = qprocess.readAllStandardOutput()
        output = handle_qbytearray(output, CondaProcess.ENCODING)
        info = json.loads(output)

        if emit:
            self.sig_finished.emit("info", unicode(info), "")

        return 'error' not in info

    def export(self, filename, name=None, prefix=None, emit=False):
        """
        Export environment by 'prefix' or 'name' as yaml 'filename'.
        """
        if name and prefix:
            raise TypeError("Exactly one of 'name' or 'prefix' is required.")

        if self._is_not_running:
            if name:
                temporal_envname = name

            if prefix:
                temporal_envname = 'tempenv' + int(random.random()*10000000)
                envs_dir = self.info()['envs_dirs'][0]
                os.symlink(prefix, os.sep.join([envs_dir, temporal_envname]))

            cmd = self._abspath(True)
            cmd.extend(['env', 'export', '--name', temporal_envname, '--file',
                        os.path.abspath(filename)])
            qprocess = QProcess()
            qprocess.start(cmd[0], cmd[1:])
            qprocess.waitForFinished()

            if prefix:
                os.unlink(os.sep.join([envs_dir, temporal_envname]))

    def update_environment(self, filename, name=None, prefix=None, emit=False):
        """
        Set environment at 'prefix' or 'name' to match 'filename' spec as yaml.
        """
        if name and prefix:
            raise TypeError("Exactly one of 'name' or 'prefix' is required.")

        if self._is_not_running:
            if name:
                temporal_envname = name

            if prefix:
                temporal_envname = 'tempenv' + int(random.random()*10000000)
                envs_dir = self.info()['envs_dirs'][0]
                os.symlink(prefix, os.sep.join([envs_dir, temporal_envname]))

            cmd = self._abspath(True)
            cmd.extend(['env', 'update', '--name', temporal_envname, '--file',
                        os.path.abspath(filename)])
            qprocess = QProcess()
            qprocess.start(cmd[0], cmd[1:])
            qprocess.waitForFinished()

            if prefix:
                os.unlink(os.sep.join([envs_dir, 'tempenv']))

    @property
    def error(self):
        return self._error

    @property
    def output(self):
        return self._output

    # --- Pip commands
    # -------------------------------------------------------------------------
    def _pip_cmd(self, name=None, prefix=None):
        """
        Get pip location based on environment `name` or `prefix`.
        """
        if (name and prefix) or not (name or prefix):
            raise TypeError("conda pip: exactly one of 'name' ""or 'prefix' "
                            "required.")

        if name and self.environment_exists(name=name):
            prefix = self.get_prefix_envname(name)

        if sys.platform == 'win32':
            python = join(prefix, 'python.exe')  # FIXME:
            pip = join(prefix, 'pip.exe')    # FIXME:
        else:
            python = join(prefix, 'bin/python')
            pip = join(prefix, 'bin/pip')

        cmd_list = [python, pip]

        return cmd_list

    def pip_list(self, name=None, prefix=None, abspath=True, emit=False):
        """
        Get list of pip installed packages.
        """
        if (name and prefix) or not (name or prefix):
            raise TypeError("conda pip: exactly one of 'name' ""or 'prefix' "
                            "required.")

        if self._is_not_running:
            cmd_list = self._abspath(abspath)
            if name:
                cmd_list.extend(['list', '--name', name])
            if prefix:
                cmd_list.extend(['list', '--prefix', prefix])

            qprocess = QProcess()
            qprocess.start(cmd_list[0], cmd_list[1:])
            qprocess.waitForFinished()
            output = qprocess.readAllStandardOutput()
            output = handle_qbytearray(output, CondaProcess.ENCODING)

            result = []
            lines = output.split('\n')

            for line in lines:
                if '<pip>' in line:
                    temp = line.split()[:-1] + ['pip']
                    result.append('-'.join(temp))

            if emit:
                self.sig_finished.emit("pip", str(result), "")

        return result

    def pip_remove(self, name=None, prefix=None, pkgs=None):
        """
        Remove a pip pacakge in given environment by 'name' or 'prefix'.
        """
        if isinstance(pkgs, list) or isinstance(pkgs, tuple):
            pkg = ' '.join(pkgs)
        else:
            pkg = pkgs

        extra_args = ['uninstall', '--yes', pkg]

        if self._is_not_running():
            self._function_called = 'pip_remove'
            self._call_pip(name=name, prefix=prefix, extra_args=extra_args)


class TestWidget(QWidget):
    """ """
    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self._parent = parent
        self.cp = CondaProcess(self)

        # Widgets
        self.button_get_conda_version = QPushButton('get_conda_version')
        self.button_info = QPushButton('info')
        self.button_get_envs = QPushButton('get envs')
        self.button_install = QPushButton('install')
        self.button_package_info = QPushButton('package info')
        self.button_linked = QPushButton('linked')
        self.button_pip = QPushButton('pip')
        self.button_pip_remove = QPushButton('pip-remove')

        self.widgets = [self.button_get_conda_version, self.button_info,
                        self.button_get_envs, self.button_install,
                        self.button_package_info, self.button_linked,
                        self.button_pip]

        # Layout setup
        layout_top = QHBoxLayout()
        layout_top.addWidget(self.button_get_conda_version)
        layout_top.addWidget(self.button_get_envs)
        layout_top.addWidget(self.button_info)
        layout_top.addWidget(self.button_install)
        layout_top.addWidget(self.button_package_info)

        layout_middle = QHBoxLayout()
        layout_middle.addWidget(self.button_linked)

        layout_bottom = QHBoxLayout()
        layout_bottom.addWidget(self.button_pip)
        layout_bottom.addWidget(self.button_pip_remove)

        layout = QVBoxLayout()
        layout.addLayout(layout_top)
        layout.addLayout(layout_middle)
        layout.addLayout(layout_bottom)

        self.setLayout(layout)

        # Signals
        self.cp.sig_started.connect(self.disable_widgets)
        self.cp.sig_finished.connect(self.on_finished)
        self.cp.sig_finished.connect(self.enable_widgets)

        self.button_get_conda_version.clicked.connect(
            self.cp.get_conda_version)
        self.button_get_envs.clicked.connect(self.cp.get_envs)
        self.button_info.clicked.connect(self.cp.info)
        self.button_install.clicked.connect(self.cp.install)
        self.button_package_info.clicked.connect(
            lambda: self.cp.package_info('spyder'))
        self.button_linked.clicked.connect(
            lambda: self.cp.linked(self.cp.ROOT_PREFIX))
        self.button_pip.clicked.connect(lambda: self.cp.pip(name='root'))
        self.button_pip_remove.clicked.connect(
            lambda: self.cp.pip_remove(name='root', pkgs=['grequests']))

    def disable_widgets(self):
        """ """
        for widget in self.widgets:
            widget.setDisabled(True)

    def enable_widgets(self):
        """ """
        for widget in self.widgets:
            widget.setEnabled(True)

    def on_finished(self, func, output, error):
        """ """
        print('stdout:\t' + str(output))
        print('stderr:\t' + str(error))
        print('function:\t' + str(func))
        print('')


def test():
    """Run conda packages widget test"""
    app = QApplication([])
    widget = TestWidget(None)
    widget.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    test()
