# -*- coding: utf-8 -*-

"""
Updated `conda-api` to include additional methods, queued worker processes
calling `QProcess` instead of `subprocess.Popen`.
"""

# Standard library imports
from os.path import basename, isdir, join
from collections import deque
import json
import os
import platform
import re
import sys
import time
import yaml

# Third party imports
from qtpy.QtCore import QByteArray, QObject, QProcess, QTimer, Signal

# Local imports
from conda_manager.utils.findpip import PIP_LIST_SCRIPT
from conda_manager.utils.logs import logger


__version__ = '1.3.0'


# --- Errors
# -----------------------------------------------------------------------------
class PipError(Exception):
    """General pip error."""
    pass


class CondaError(Exception):
    """General Conda error."""
    pass


class CondaProcessWorker(CondaError):
    """General Conda error."""
    pass


class CondaEnvExistsError(CondaError):
    """Conda environment already exists."""
    pass


# --- Helpers
# -----------------------------------------------------------------------------
PY2 = sys.version[0] == '2'
PY3 = sys.version[0] == '3'
DEBUG = False


def to_text_string(obj, encoding=None):
    """Convert `obj` to (unicode) text string."""
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
    """
    Qt/Python3 compatibility helper.
    """
    if isinstance(obj, QByteArray):
        obj = obj.data()

    return to_text_string(obj, encoding=encoding)


class ProcessWorker(QObject):
    """
    """
    sig_finished = Signal(object, object, object)
    sig_partial = Signal(object, object, object)

    def __init__(self, cmd_list, parse=False, pip=False, callback=None,
                 extra_kwargs={}):
        super(ProcessWorker, self).__init__()
        self._result = None
        self._cmd_list = cmd_list
        self._parse = parse
        self._pip = pip
        self._conda = not pip
        self._callback = callback
        self._fired = False
        self._communicate_first = False
        self._partial_stdout = None
        self._extra_kwargs = extra_kwargs

        self._timer = QTimer()
        self._process = QProcess()

        self._timer.setInterval(150)

        self._timer.timeout.connect(self._communicate)
        # self._process.finished.connect(self._communicate)
        self._process.readyReadStandardOutput.connect(self._partial)

    def _partial(self):
        raw_stdout = self._process.readAllStandardOutput()
        stdout = handle_qbytearray(raw_stdout, _CondaAPI.UTF8)

        json_stdout = stdout.replace('\n\x00', '')
        try:
            json_stdout = json.loads(json_stdout)
        except Exception:
            json_stdout = stdout

        if self._partial_stdout is None:
            self._partial_stdout = stdout
        else:
            self._partial_stdout += stdout

        self.sig_partial.emit(self, json_stdout, None)

    def _communicate(self):
        """
        """
        if not self._communicate_first:
            if self._process.state() == QProcess.NotRunning:
                self.communicate()
        elif self._fired:
            self._timer.stop()

    def communicate(self):
        """
        """
        self._communicate_first = True
        self._process.waitForFinished()

        if self._partial_stdout is None:
            raw_stdout = self._process.readAllStandardOutput()
            stdout = handle_qbytearray(raw_stdout, _CondaAPI.UTF8)
        else:
            stdout = self._partial_stdout

        raw_stderr = self._process.readAllStandardError()
        stderr = handle_qbytearray(raw_stderr, _CondaAPI.UTF8)
        result = [stdout.encode(_CondaAPI.UTF8), stderr.encode(_CondaAPI.UTF8)]

        # FIXME: Why does anaconda client print to stderr???
        if PY2:
            stderr = stderr.decode()
        if 'using anaconda cloud api site' not in stderr.lower():
            if stderr.strip() and self._conda:
                raise Exception('{0}:\n'
                                'STDERR:\n{1}\nEND'
                                ''.format(' '.join(self._cmd_list),
                                          stderr))
#            elif stderr.strip() and self._pip:
#                raise PipError(self._cmd_list)
        else:
            result[-1] = ''

        if self._parse and stdout:
            try:
                result = json.loads(stdout), result[-1]
            except ValueError as error:
                result = stdout, error

            if 'error' in result[0]:
                error = '{0}: {1}'.format(" ".join(self._cmd_list),
                                          result[0]['error'])
                result = result[0], error

        if self._callback:
            result = self._callback(result[0], result[-1],
                                    **self._extra_kwargs), result[-1]

        self._result = result
        self.sig_finished.emit(self, result[0], result[-1])

        if result[-1]:
            logger.error(str(('error', result[-1])))

        self._fired = True

        return result

    def close(self):
        """
        """
        self._process.close()

    def is_finished(self):
        """
        """
        return self._process.state() == QProcess.NotRunning and self._fired

    def start(self):
        """
        """
        logger.debug(str(' '.join(self._cmd_list)))

        if not self._fired:
            self._partial_ouput = None
            self._process.start(self._cmd_list[0], self._cmd_list[1:])
            self._timer.start()
        else:
            raise CondaProcessWorker('A Conda ProcessWorker can only run once '
                                     'per method call.')


# --- API
# -----------------------------------------------------------------------------
class _CondaAPI(QObject):
    """
    """
    ROOT_PREFIX = None
    ENCODING = 'ascii'
    UTF8 = 'utf-8'
    DEFAULT_CHANNELS = ['https://repo.continuum.io/pkgs/pro',
                        'https://repo.continuum.io/pkgs/free']

    def __init__(self, parent=None):
        super(_CondaAPI, self).__init__()
        self._parent = parent
        self._queue = deque()
        self._timer = QTimer()
        self._current_worker = None
        self._workers = []

        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._clean)

        self.set_root_prefix()

    def _clean(self):
        """
        Periodically check for inactive workers and remove their references.
        """
        if self._workers:
            for w in self._workers:
                if w.is_finished():
                    self._workers.remove(w)
        else:
            self._current_worker = None
            self._timer.stop()

    def _start(self):
        """
        """
        if len(self._queue) == 1:
            self._current_worker = self._queue.popleft()
            self._workers.append(self._current_worker)
            self._current_worker.start()
            self._timer.start()

    def is_active(self):
        """
        Check if a worker is still active.
        """
        return len(self._workers) == 0

    def terminate_all_processes(self):
        """
        Kill all working processes.
        """
        for worker in self._workers:
            worker.close()

    # --- Conda api
    # -------------------------------------------------------------------------
    def _call_conda(self, extra_args, abspath=True, parse=False,
                    callback=None):
        """
        Call conda with the list of extra arguments, and return the worker.
        The result can be force by calling worker.communicate(), which returns
        the tuple (stdout, stderr).
        """
        if abspath:
            if sys.platform == 'win32':
                python = join(self.ROOT_PREFIX, 'python.exe')
                conda = join(self.ROOT_PREFIX, 'Scripts',
                             'conda-script.py')
            else:
                python = join(self.ROOT_PREFIX, 'bin/python')
                conda = join(self.ROOT_PREFIX, 'bin/conda')
            cmd_list = [python, conda]
        else:
            # Just use whatever conda is on the path
            cmd_list = ['conda']

        cmd_list.extend(extra_args)

        process_worker = ProcessWorker(cmd_list, parse=parse,
                                       callback=callback)
        process_worker.sig_finished.connect(self._start)
        self._queue.append(process_worker)
        self._start()

        return process_worker

    def _call_and_parse(self, extra_args, abspath=True, callback=None):
        """
        """
        return self._call_conda(extra_args, abspath=abspath, parse=True,
                                callback=callback)

    def _setup_install_commands_from_kwargs(self, kwargs, keys=tuple()):
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

    def set_root_prefix(self, prefix=None):
        """
        Set the prefix to the root environment (default is /opt/anaconda).
        This function should only be called once (right after importing
        conda_api).
        """
        if prefix:
            self.ROOT_PREFIX = prefix
        else:
            # Find some conda instance, and then use info to get 'root_prefix'
            worker = self._call_and_parse(['info', '--json'], abspath=False)
            info = worker.communicate()[0]
            self.ROOT_PREFIX = info['root_prefix']

    def get_conda_version(self):
        """
        Return the version of conda being used (invoked) as a string.
        """
        return self._call_conda(['--version'],
                                callback=self._get_conda_version)

    def _get_conda_version(self, stdout, stderr):
        # argparse outputs version to stderr in Python < 3.4.
        # http://bugs.python.org/issue18920
        pat = re.compile(r'conda:?\s+(\d+\.\d\S+|unknown)')
        m = pat.match(stderr.decode().strip())
        if m is None:
            m = pat.match(stdout.decode().strip())

        if m is None:
            raise Exception('output did not match: {0}'.format(stderr))

        return m.group(1)

    def get_envs(self):
        """
        Return all of the (named) environment (this does not include the root
        environment), as a list of absolute path to their prefixes.
        """
        logger.debug('')
#        return self._call_and_parse(['info', '--json'],
#                                    callback=lambda o, e: o['envs'])
        envs = os.listdir(os.sep.join([self.ROOT_PREFIX, 'envs']))
        envs = [os.sep.join([self.ROOT_PREFIX, 'envs', i]) for i in envs]

        valid_envs = [e for e in envs if os.path.isdir(e) and
                      self.environment_exists(prefix=e)]

        return valid_envs

    def get_prefix_envname(self, name):
        """
        Given the name of an environment return its full prefix path, or None
        if it cannot be found.
        """
        prefix = None
        if name == 'root':
            prefix = self.ROOT_PREFIX

#        envs, error = self.get_envs().communicate()
        envs = self.get_envs()
        for p in envs:
            if basename(p) == name:
                prefix = p

        return prefix

    def linked(self, prefix):
        """
        Return the (set of canonical names) of linked packages in `prefix`.
        """
        logger.debug(str(prefix))

        if not isdir(prefix):
            raise Exception('no such directory: {0}'.format(prefix))

        meta_dir = join(prefix, 'conda-meta')
        if not isdir(meta_dir):
            # We might have nothing in linked (and no conda-meta directory)
            return set()

        return set(fn[:-5] for fn in os.listdir(meta_dir)
                   if fn.endswith('.json'))

    def split_canonical_name(self, cname):
        """
        Split a canonical package name into (name, version, build) strings.
        """
        return tuple(cname.rsplit('-', 2))

    def info(self, abspath=True):
        """
        Return a dictionary with configuration information.
        No guarantee is made about which keys exist.  Therefore this function
        should only be used for testing and debugging.
        """
        logger.debug(str(''))
        return self._call_and_parse(['info', '--json'], abspath=abspath)

    def package_info(self, package, abspath=True):
        """
        Return a dictionary with package information.
        """
        return self._call_and_parse(['info', package, '--json'],
                                    abspath=abspath)

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
            cmd_list.extend(['--platform', kwargs.pop('platform')])

        cmd_list.extend(
            self._setup_install_commands_from_kwargs(
                kwargs,
                ('canonical', 'unknown', 'use_index_cache', 'outdated',
                 'override_channels')))

        return self._call_and_parse(cmd_list,
                                    abspath=kwargs.get('abspath', True))

    def create(self, name=None, prefix=None, pkgs=None, channels=None):
        """
        Create an environment either by name or path with a specified set of
        packages.
        """
        logger.debug(str((prefix, pkgs, channels)))

        # TODO: Fix temporal hack
        if not pkgs or not isinstance(pkgs, (list, tuple, str)):
            raise TypeError('must specify a list of one or more packages to '
                            'install into new environment')

        cmd_list = ['create', '--yes', '--quiet', '--json', '--mkdir']
        if name:
            ref = name
            search = [os.path.join(d, name) for d in
                      self.info().communicate()[0]['envs_dirs']]
            cmd_list.extend(['--name', name])
        elif prefix:
            ref = prefix
            search = [prefix]
            cmd_list.extend(['--prefix', prefix])
        else:
            raise TypeError('must specify either an environment name or a '
                            'path for new environment')

        if any(os.path.exists(prefix) for prefix in search):
            raise CondaEnvExistsError('Conda environment {0} already '
                                      'exists'.format(ref))

        # TODO: Fix temporal hack
        if isinstance(pkgs, (list, tuple)):
            cmd_list.extend(pkgs)
        elif isinstance(pkgs, str):
            cmd_list.extend(['--file', pkgs])

        # TODO: Check if correct
        if channels:
            cmd_list.extend(['--override-channels'])

            for channel in channels:
                cmd_list.extend(['--channel'])
                cmd_list.extend([channel])

        return self._call_and_parse(cmd_list)

    def parse_token_channel(self, channel, token):
        """
        Adapt a channel to include the authentication token of the logged
        user.

        Ignore default channels
        """
        if token and channel not in self.DEFAULT_CHANNELS:
            url_parts = channel.split('/')
            start = url_parts[:-1]
            middle = 't/{0}'.format(token)
            end = url_parts[-1]
            token_channel = '{0}/{1}/{2}'.format('/'.join(start), middle, end)
            return token_channel
        else:
            return channel

    def install(self, name=None, prefix=None, pkgs=None, dep=True,
                channels=None, token=None):
        """
        Install packages into an environment either by name or path with a
        specified set of packages.

        If token is specified, the channels different from the defaults will
        get the token appended.
        """
        logger.debug(str((prefix, pkgs, channels)))

        # TODO: Fix temporal hack
        if not pkgs or not isinstance(pkgs, (list, tuple, str)):
            raise TypeError('must specify a list of one or more packages to '
                            'install into existing environment')

        cmd_list = ['install', '--yes', '--json', '--force-pscheck']
        if name:
            cmd_list.extend(['--name', name])
        elif prefix:
            cmd_list.extend(['--prefix', prefix])
        else:
            # Just install into the current environment, whatever that is
            pass

        # TODO: Check if correct
        if channels:
            cmd_list.extend(['--override-channels'])

            for channel in channels:
                cmd_list.extend(['--channel'])
                channel = self.parse_token_channel(channel, token)
                cmd_list.extend([channel])

        # TODO: Fix temporal hack
        if isinstance(pkgs, (list, tuple)):
            cmd_list.extend(pkgs)
        elif isinstance(pkgs, str):
            cmd_list.extend(['--file', pkgs])

        if not dep:
            cmd_list.extend(['--no-deps'])

        return self._call_and_parse(cmd_list)

    def update(self, *pkgs, **kwargs):
        """
        Update package(s) (in an environment) by name.
        """
        cmd_list = ['update', '--json', '--quiet', '--yes']

        if not pkgs and not kwargs.get('all'):
            raise TypeError("Must specify at least one package to update, or "
                            "all=True.")

        cmd_list.extend(
            self._setup_install_commands_from_kwargs(
                kwargs,
                ('dry_run', 'no_deps', 'override_channels',
                 'no_pin', 'force', 'all', 'use_index_cache', 'use_local',
                 'alt_hint')))

        cmd_list.extend(pkgs)

        return self._call_and_parse(cmd_list, abspath=kwargs.get('abspath',
                                                                 True))

    def remove(self, name=None, prefix=None, pkgs=None, all_=False):
        """
        Remove a package (from an environment) by name.

        Returns {
            success: bool, (this is always true),
            (other information)
        }
        """
        logger.debug(str((prefix, pkgs)))

        cmd_list = ['remove', '--json', '--quiet', '--yes']

        if not pkgs and not all_:
            raise TypeError("Must specify at least one package to remove, or "
                            "all=True.")

        if name:
            cmd_list.extend(['--name', name])
        elif prefix:
            cmd_list.extend(['--prefix', prefix])
        else:
            raise TypeError('must specify either an environment name or a '
                            'path for package removal')

        if all_:
            cmd_list.extend(['--all'])
        else:
            cmd_list.extend(pkgs)

        return self._call_and_parse(cmd_list)

    def remove_environment(self, name=None, path=None, **kwargs):
        """
        Remove an environment entirely.

        See ``remove``.
        """
        return self.remove(name=name, path=path, all=True, **kwargs)

    def clone_environment(self, clone, name=None, prefix=None, **kwargs):
        """
        Clone the environment `clone` into `name` or `prefix`.
        """
        cmd_list = ['create', '--json', '--quiet']

        if (name and prefix) or not (name or prefix):
            raise TypeError("conda clone_environment: exactly one of `name` "
                            "or `path` required")

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

        return self._call_and_parse(cmd_list, abspath=kwargs.get('abspath',
                                                                 True))

    # FIXME:
    def process(self, name=None, prefix=None, cmd=None):
        """
        Create a Popen process for cmd using the specified args but in the
        conda environment specified by name or prefix.

        The returned object will need to be invoked with p.communicate() or
        similar.
        """
        if bool(name) == bool(prefix):
            raise TypeError('exactly one of name or prefix must be specified')

        if not cmd:
            raise TypeError('cmd to execute must be specified')

        if not args:
            args = []

        if name:
            prefix = self.get_prefix_envname(name)

        conda_env = dict(os.environ)
        sep = os.pathsep

        if sys.platform == 'win32':
            conda_env['PATH'] = join(prefix,
                                     'Scripts') + sep + conda_env['PATH']
        else:
            # Unix
            conda_env['PATH'] = join(prefix, 'bin') + sep + conda_env['PATH']

        conda_env['PATH'] = prefix + os.pathsep + conda_env['PATH']

        cmd_list = [cmd]
        cmd_list.extend(args)

#         = self.subprocess.process(cmd_list, env=conda_env, stdin=stdin,
#                                        stdout=stdout, stderr=stderr)

    def _setup_config_from_kwargs(self, kwargs):
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

        return self._call_and_parse(cmd_list,
                                    abspath=kwargs.get('abspath', True),
                                    callback=lambda o, e: o['rc_path'])

    def config_get(self, *keys, **kwargs):
        """
        Get the values of configuration keys.

        Returns a dictionary of values. Note, the key may not be in the
        dictionary if the key wasn't set in the configuration file.
        """
        cmd_list = ['config', '--get']
        cmd_list.extend(keys)
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        return self._call_and_parse(cmd_list,
                                    abspath=kwargs.get('abspath', True),
                                    callback=lambda o, e: o['get'])

    def config_set(self, key, value, **kwargs):
        """
        Set a key to a (bool) value.

        Returns a list of warnings Conda may have emitted.
        """
        cmd_list = ['config', '--set', key, str(value)]
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        return self._call_and_parse(
            cmd_list,
            abspath=kwargs.get('abspath', True),
            callback=lambda o, e: o.get('warnings', []))

    def config_add(self, key, value, **kwargs):
        """
        Add a value to a key.

        Returns a list of warnings Conda may have emitted.
        """
        cmd_list = ['config', '--add', key, value]
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        return self._call_and_parse(
            cmd_list,
            abspath=kwargs.get('abspath', True),
            callback=lambda o, e: o.get('warnings', []))

    def config_remove(self, key, value, **kwargs):
        """
        Remove a value from a key.

        Returns a list of warnings Conda may have emitted.
        """
        cmd_list = ['config', '--remove', key, value]
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        return self._call_and_parse(
            cmd_list,
            abspath=kwargs.get('abspath', True),
            callback=lambda o, e: o.get('warnings', []))

    def config_delete(self, key, **kwargs):
        """
        Remove a key entirely.

        Returns a list of warnings Conda may have emitted.
        """
        cmd_list = ['config', '--remove-key', key]
        cmd_list.extend(self._setup_config_from_kwargs(kwargs))

        return self._call_and_parse(
            cmd_list,
            abspath=kwargs.get('abspath', True),
            callback=lambda o, e: o.get('warnings', []))

    def run(self, command, abspath=True):
        """
        Launch the specified app by name or full package name.

        Returns a dictionary containing the key "fn", whose value is the full
        package (ending in ``.tar.bz2``) of the app.
        """
        cmd_list = ['run', '--json', command]

        return self._call_and_parse(cmd_list, abspath=abspath)

    # --- Additional methods
    # -----------------------------------------------------------------------------
    def dependencies(self, name=None, prefix=None, pkgs=None, channels=None,
                     dep=True):
        """
        Get dependenciy list for packages to be installed into an environment
        defined either by 'name' or 'prefix'.
        """
        if not pkgs or not isinstance(pkgs, (list, tuple)):
            raise TypeError('must specify a list of one or more packages to '
                            'install into existing environment')

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

        # TODO: Check if correct
        if channels:
            cmd_list.extend(['--override-channels'])

            for channel in channels:
                cmd_list.extend(['--channel'])
                cmd_list.extend([channel])

        return self._call_and_parse(cmd_list)

    def environment_exists(self, name=None, prefix=None, abspath=True):
        """
        Check if an environment exists by 'name' or by 'prefix'. If query is
        by 'name' only the default conda environments directory is searched.
        """
        logger.debug(str((name, prefix)))

        if name and prefix:
            raise TypeError("Exactly one of 'name' or 'prefix' is required.")

        if name:
            prefix = self.get_prefix_envname(name)

        if prefix is None:
            prefix = self.ROOT_PREFIX

        return os.path.isdir(os.path.join(prefix, 'conda-meta'))

    def clear_lock(self, abspath=True):
        """
        Clean any conda lock in the system.
        """
        cmd_list = ['clean', '--lock', '--json']
        return self._call_and_parse(cmd_list, abspath=abspath)

    def package_version(self, prefix=None, name=None, pkg=None):
        """
        """
        package_versions = {}

        if name and prefix:
            raise TypeError("Exactly one of 'name' or 'prefix' is required.")

        if name:
            prefix = self.get_prefix_envname(name)

        if self.environment_exists(prefix=prefix):

            for package in self.linked(prefix):
                if pkg in package:
                    n, v, b = self.split_canonical_name(package)
                    package_versions[n] = v

        return package_versions.get(pkg, None)

    def get_platform(self):
        """
        Get platform of current system (system and bitness).
        """
        _sys_map = {'linux2': 'linux', 'linux': 'linux',
                    'darwin': 'osx', 'win32': 'win', 'openbsd5': 'openbsd'}

        non_x86_linux_machines = {'armv6l', 'armv7l', 'ppc64le'}
        sys_platform = _sys_map.get(sys.platform, 'unknown')
        bits = 8 * tuple.__itemsize__

        if (sys_platform == 'linux' and
                platform.machine() in non_x86_linux_machines):
            arch_name = platform.machine()
            subdir = 'linux-{0}'.format(arch_name)
        else:
            arch_name = {64: 'x86_64', 32: 'x86'}[bits]
            subdir = '{0}-{1}'.format(sys_platform, bits)

        return subdir

    def get_condarc_channels(self):
        """
        Returns all the channel urls defined in .condarc using the defined
        `channel_alias`.

        If no condarc file is found, use the default channels.
        """
        # First get the location of condarc file and parse it to get
        # the channel alias and the channels.
        default_channel_alias = 'https://conda.anaconda.org'
        default_urls = ['https://repo.continuum.io/pkgs/free',
                        'https://repo.continuum.io/pkgs/pro']

        condarc_path = os.path.abspath(os.path.expanduser('~/.condarc'))
        channels = default_urls[:]

        if not os.path.isfile(condarc_path):
            condarc = None
            channel_alias = default_channel_alias
        else:
            with open(condarc_path, 'r') as f:
                data = f.read()
                condarc = yaml.load(data)
                channels += condarc.get('channels', [])
                channel_alias = condarc.get('channel_alias',
                                            default_channel_alias)

        if channel_alias[-1] == '/':
            template = "{0}{1}"
        else:
            template = "{0}/{1}"

        if 'defaults' in channels:
            channels.remove('defaults')

        channel_urls = []
        for channel in channels:
            if not channel.startswith('http'):
                channel_url = template.format(channel_alias, channel)
            else:
                channel_url = channel
            channel_urls.append(channel_url)

        return channel_urls

    # --- Pip commands
    # -------------------------------------------------------------------------
    def _call_pip(self, name=None, prefix=None, extra_args=None,
                  callback=None):
        """ """
        cmd_list = self._pip_cmd(name=name, prefix=prefix)
        cmd_list.extend(extra_args)

        process_worker = ProcessWorker(cmd_list, pip=True, callback=callback)
        process_worker.sig_finished.connect(self._start)
        self._queue.append(process_worker)
        self._start()

        return process_worker

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
            pip = join(prefix, 'pip.exe')        # FIXME:
        else:
            python = join(prefix, 'bin/python')
            pip = join(prefix, 'bin/pip')

        cmd_list = [python, pip]

        return cmd_list

    def pip_list(self, name=None, prefix=None, abspath=True):
        """
        Get list of pip installed packages.
        """
        if (name and prefix) or not (name or prefix):
            raise TypeError("conda pip: exactly one of 'name' ""or 'prefix' "
                            "required.")

        if name:
            prefix = self.get_prefix_envname(name)

        pip_command = os.sep.join([prefix, 'bin', 'python'])
        cmd_list = [pip_command, PIP_LIST_SCRIPT]
        process_worker = ProcessWorker(cmd_list, pip=True, parse=True,
                                       callback=self._pip_list,
                                       extra_kwargs={'prefix': prefix})
        process_worker.sig_finished.connect(self._start)
        self._queue.append(process_worker)
        self._start()

        return process_worker

#        if name:
#            cmd_list = ['list', '--name', name]
#        if prefix:
#            cmd_list = ['list', '--prefix', prefix]

#        return self._call_conda(cmd_list, abspath=abspath,
#                                callback=self._pip_list)

    def _pip_list(self, stdout, stderr, prefix=None):
        """
        """
        result = stdout  # A dict
        linked = self.linked(prefix)

        pip_only = []

        linked_names = [self.split_canonical_name(l)[0] for l in linked]

        for pkg in result:
            name = self.split_canonical_name(pkg)[0]
            if name not in linked_names:
                pip_only.append(pkg)
            # FIXME: NEED A MORE ROBUST WAY!
#            if '<pip>' in line and '#' not in line:
#                temp = line.split()[:-1] + ['pip']
#                temp = '-'.join(temp)
#                if '-(' in temp:
#                    start = temp.find('-(')
#                    end = temp.find(')')
#                    substring = temp[start:end+1]
#                    temp = temp.replace(substring, '')
#                result.append(temp)

        return pip_only

    def pip_remove(self, name=None, prefix=None, pkgs=None):
        """
        Remove a pip package in given environment by `name` or `prefix`.
        """
        logger.debug(str((prefix, pkgs)))

        if isinstance(pkgs, list) or isinstance(pkgs, tuple):
            pkg = ' '.join(pkgs)
        else:
            pkg = pkgs

        extra_args = ['uninstall', '--yes', pkg]

        return self._call_pip(name=name, prefix=prefix, extra_args=extra_args)

    def pip_search(self, search_string=None):
        """
        Search for pip installable python packages in PyPI matching
        `search_string`.
        """
        extra_args = ['search', search_string]
        return self._call_pip(name='root', extra_args=extra_args,
                              callback=self._pip_search)

        # if stderr:
        #     raise PipError(stderr)
        # You are using pip version 7.1.2, however version 8.0.2 is available.
        # You should consider upgrading via the 'pip install --upgrade pip'
        # command.

    def _pip_search(self, stdout, stderr):
        result = {}
        lines = to_text_string(stdout).split('\n')
        while '' in lines:
            lines.remove('')

        for line in lines:
            if ' - ' in line:
                parts = line.split(' - ')
                name = parts[0].strip()
                description = parts[1].strip()
                result[name] = description

        return result


CONDA_API = None


def CondaAPI():
    global CONDA_API

    if CONDA_API is None:
        CONDA_API = _CondaAPI()

    return CONDA_API

COUNTER = 0


def ready_print(worker, output, error):
    global COUNTER
    COUNTER += 1
    print(COUNTER, output, error)


def test():
    """
    """
    from conda_manager.utils.qthelpers import qapplication

    app = qapplication()
    conda_api = CondaAPI()
#    print(conda_api.get_condarc_channels())
#    worker = conda_api.info()
##    worker.sig_finished.connect(ready_print)
#    worker = conda_api.info()
#    worker = conda_api.info()
#    worker = conda_api.info()
#    worker = conda_api.info()
#    worker = conda_api.info()
#    worker = conda_api.info()
#    worker = conda_api.info()
#    worker = conda_api.info()
#    worker = conda_api.info()
#    worker = conda_api.info()
#    worker = conda_api.pip_search('spyder')
#    worker.sig_finished.connect(ready_print)
    worker = conda_api.pip_list(name='py3')
    worker.sig_finished.connect(ready_print)
#    print(conda_api.package_version(name='root', pkg='spyder'))

    app.exec_()


if __name__ == '__main__':
    test()
