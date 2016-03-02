# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

"""
"""

# Standard library imports
from collections import deque
import bz2
import json
import os

# Third party imports
from qtpy.QtCore import QObject, QThread, QTimer, Signal
import binstar_client

# Local imports
from conda_manager.utils import sort_versions
from conda_manager.utils import constants as C
from conda_manager.utils.logs import logger


class ClientWorker(QObject):
    sig_finished = Signal(object, object, object)

    def __init__(self, method, args, kwargs):
        super(ClientWorker, self).__init__()
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self._is_finished = False

    def is_finished(self):
        """
        Return wether or not the worker has finished or not executing its
        current process.
        """
        return self._is_finished

    def start(self):
        """
        Start the worker process.
        """
        error, output = None, None
        try:
            output = self.method(*self.args, **self.kwargs)
        except Exception as err:
            logger.debug(str((self.method.__module__, self.method.__name___,
                              err)))
            try:
                error = err[0]
            except Exception:
                error = err.message

        self.sig_finished.emit(self, output, error)
        self._is_finished = True


class _ClientAPI(QObject):
    """
    """

    def __init__(self):
        super(QObject, self).__init__()
        self._anaconda_client_api = binstar_client.Binstar(
            token=None,
            domain='https://api.anaconda.org')

        self._queue = deque()
        self._threads = []
        self._workers = []
        self._timer = QTimer()

        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._clean)

    def _clean(self):
        """
        Periodically check for inactive workers and remove their references.
        """
        if self._workers:
            for w in self._workers:
                if w.is_finished():
                    self._workers.remove(w)

        if self._threads:
            for t in self._threads:
                if t.isFinished():
                    self._threads.remove(t)
        else:
            self._timer.stop()

    def _start(self):
        """
        """
        if len(self._queue) == 1:
            thread = self._queue.popleft()
            thread.start()
            self._timer.start()

    def _create_worker(self, method, *args, **kwargs):
        """
        Create a worker for this client to be run in a separate thread.
        """
        # FIXME: this might be heavy...
        thread = QThread()
        worker = ClientWorker(method, args, kwargs)
        worker.moveToThread(thread)
        worker.sig_finished.connect(self._start)
        worker.sig_finished.connect(thread.quit)
        thread.started.connect(worker.start)
        self._queue.append(thread)
        self._threads.append(thread)
        self._workers.append(worker)
        self._start()
        return worker

    def _load_repodata(self, filepaths, extra_data={}, metadata={}):
        """
        Load all the available pacakges information for downloaded repodata
        files (repo.continuum.io), additional data provided (anaconda cloud),
        and additional metadata and merge into a single set of packages and
        apps.
        """
        repodata = []
        for filepath in filepaths:
            compressed = filepath.endswith('.bz2')
            mode = 'rb' if filepath.endswith('.bz2') else 'r'

            if os.path.isfile(filepath):
                with open(filepath, mode) as f:
                    raw_data = f.read()

                if compressed:
                    data = bz2.decompress(raw_data)
                else:
                    data = raw_data

                try:
                    data = json.loads(data)
                except Exception as error:
                    logger.error(str(error))
                    data = {}

                repodata.append(data)

        all_packages = {}
        for data in repodata:
            packages = data.get('packages', {})
            for canonical_name in packages:
                data = packages[canonical_name]
                name, version, b = tuple(canonical_name.rsplit('-', 2))

                if name not in all_packages:
                    all_packages[name] = {'versions': set(),
                                          'size': {},
                                          'type': {},
                                          'app_entry': {},
                                          'app_type': {},
                                          }
                elif name in metadata:
                    temp_data = all_packages[name]
                    temp_data['home'] = metadata[name].get('home', '')
                    temp_data['license'] = metadata[name].get('license', '')
                    temp_data['summary'] = metadata[name].get('summary', '')
                    temp_data['latest_version'] = metadata[name].get('version')
                    all_packages[name] = temp_data

                all_packages[name]['versions'].add(version)
                all_packages[name]['size'][version] = data['size']
                all_packages[name]['type'][version] = data.get('type', None)
                all_packages[name]['app_entry'][version] = data.get('app_entry',
                                                                    None)
                all_packages[name]['app_type'][version] = data.get('app_type',
                                                                   None)

        all_apps = {}
        for name in all_packages:
            versions = sort_versions(list(all_packages[name]['versions']))
            all_packages[name]['versions'] = versions

            for version in versions:
                is_app = all_packages[name]['type'][version]
                if is_app:
                    all_apps[name] = all_packages[name]

        return all_packages, all_apps

    def _prepare_model_data(self, packages, linked, pip):
        """
        """
        data = []

        linked_packages = {}
        for canonical_name in linked:
            name, version, b = tuple(canonical_name.rsplit('-', 2))
            linked_packages[name] = {'version': version}

        pip_packages = {}
        for canonical_name in pip:
            name, version, b = tuple(canonical_name.rsplit('-', 2))
            pip_packages[name] = {'version': version}

        packages_names = sorted(list(set(list(linked_packages.keys()) +
                                         list(pip_packages.keys()) +
                                         list(packages.keys()))))

        for name in packages_names:
            p_data = packages.get(name, None)

            summary = p_data.get('summary', '') if p_data else ''
            url = p_data.get('home', '') if p_data else ''
            license_ = p_data.get('license', '') if p_data else ''
            versions = p_data.get('versions', '') if p_data else []
            version = p_data.get('latest_version', '') if p_data else ''

            if name in pip_packages:
                type_ = C.PIP_PACKAGE
                version = pip_packages[name].get('version', '')
                status = C.INSTALLED
            elif name in linked_packages:
                type_ = C.CONDA_PACKAGE
                version = linked_packages[name].get('version', '')
                status = C.INSTALLED

                if version in versions:
                    vers = versions
                    upgradable = not version == vers[-1] and len(vers) != 1
                    downgradable = not version == vers[0] and len(vers) != 1

                    if upgradable and downgradable:
                        status = C.MIXGRADABLE
                    elif upgradable:
                        status = C.UPGRADABLE
                    elif downgradable:
                        status = C.DOWNGRADABLE
            else:
                type_ = C.CONDA_PACKAGE
                status = C.NOT_INSTALLED

                if version == '' and len(versions) != 0:
                    version = versions[-1]

            row = {C.COL_ACTION: C.ACTION_NONE,
                   C.COL_PACKAGE_TYPE: type_,
                   C.COL_NAME: name,
                   C.COL_DESCRIPTION: summary.capitalize(),
                   C.COL_VERSION: version,
                   C.COL_STATUS: status,
                   C.COL_URL: url,
                   C.COL_LICENSE: license_,
                   C.COL_INSTALL: False,
                   C.COL_REMOVE: False,
                   C.COL_UPGRADE: False,
                   C.COL_DOWNGRADE: False,
                   C.COL_ACTION_VERSION: None
                   }

            data.append(row)
        return data

    # --- Public API
    # -------------------------------------------------------------------------
    def login(self, username, password, application, application_url):
        """
        Login to anaconda cloud.
        """
        logger.debug(str((username, application, application_url)))
        method = self._anaconda_client_api.authenticate
        return self._create_worker(method, username, password, application,
                                   application_url)

    def logout(self):
        """
        Logout from anaconda cloud.
        """
        logger.debug('')
        method = self._anaconda_client_api.remove_authentication
        return self._create_worker(method)

    def load_repodata(self, filepaths, extra_data={}, metadata={}):
        """
        Load all the available pacakges information for downloaded repodata
        files (repo.continuum.io), additional data provided (anaconda cloud),
        and additional metadata and merge into a single set of packages and
        apps.
        """
        logger.debug(str((filepaths)))
        method = self._load_repodata
        return self._create_worker(method, filepaths, extra_data=extra_data,
                                   metadata=metadata)

    def prepare_model_data(self, packages, linked, pip):
        """
        """
        logger.debug('')
        method = self._prepare_model_data
        return self._create_worker(method, packages, linked, pip)

    def set_domain(self, domain, token=None):
        """
        """
        logger.debug(str((domain)))
        self._anaconda_client_api = binstar_client.Binstar(token=token,
                                                           domain=domain)


CLIENT_API = None


def ClientAPI():
    global CLIENT_API

    if CLIENT_API is None:
        CLIENT_API = _ClientAPI()

    return CLIENT_API


def test():
    from anaconda_ui.utils.qthelpers import qapplication
    app = qapplication()
    api = ClientAPI()
    api.login('goanpeca', 'asdasd', 'baby', '')
    api.login('bruce', 'asdasd', 'baby', '')
    api.login('asdkljasdh', 'asdasd', 'baby', '')
    api.login('asdkljasdh', 'asdasd', 'baby', '')
    api.login('asdkljasdh', 'asdasd', 'baby', '')
    api.login('asdkljasdh', 'asdasd', 'baby', '')
    api.login('asdkljasdh', 'asdasd', 'baby', '')
    api.login('asdkljasdh', 'asdasd', 'baby', '')
    api.login('asdkljasdh', 'asdasd', 'baby', '')
    api.login('asdkljasdh', 'asdasd', 'baby', '')
#    api.logout()
    app.exec_()


if __name__ == '__main__':
    test()
