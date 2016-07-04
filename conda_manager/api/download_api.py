# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright © 2015- The Spyder Development Team
# Copyright © 2014-2015 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License
# -----------------------------------------------------------------------------
"""Worker threads for downloading files."""

# Standard library imports
from collections import deque
import json
import os
import re
import sys

# Third party imports
from qtpy.QtCore import QByteArray, QObject, QThread, QTimer, QUrl, Signal
from qtpy.QtNetwork import (QNetworkAccessManager, QNetworkProxy,
                            QNetworkProxyFactory, QNetworkRequest)
import requests

# Local imports
from anaconda_navigator.api.conda_api import CondaAPI
from anaconda_navigator.utils.logs import logger
from anaconda_navigator.utils.py3compat import to_text_string

PROXY_RE = re.compile(r'(?P<scheme>.*?)://'
                      '((?P<username>.*):(?P<password>.*)@)?'
                      '(?P<host_port>.*)')


def handle_qbytearray(obj, encoding):
    """Qt/Python3 compatibility helper."""
    if isinstance(obj, QByteArray):
        obj = obj.data()

    return to_text_string(obj, encoding=encoding)


def process_proxy_servers(proxy_settings):
    """Split the proxy conda configuration to be used by the proxy factory."""
    proxy_settings_dic = {}

    for key in proxy_settings:
        proxy = proxy_settings[key]
        proxy_config = [m.groupdict() for m in PROXY_RE.finditer(proxy)]
        if proxy_config:
            proxy_config = proxy_config[0]
            host_port = proxy_config.pop('host_port')
            if ':' in host_port:
                host, port = host_port.split(':')
            else:
                host, port = host_port, None
            proxy_config['host'] = host
            proxy_config['port'] = int(port) if port else None
            proxy_settings_dic[key] = proxy_config
            proxy_config['full'] = proxy_settings[key]

    return proxy_settings_dic


class NetworkProxyFactory(QNetworkProxyFactory):
    """Proxy factory to handle different proxy configuration."""

    def __init__(self, *args, **kwargs):
        """Proxy factory to handle different proxy configuration."""
        self._load_rc_func = kwargs.pop('load_rc_func', None)
        super(NetworkProxyFactory, self).__init__(*args, **kwargs)

    @property
    def proxy_servers(self):
        """
        Return the proxy servers available.

        First env variables will be searched and updated with values from
        condarc config file.
        """
        proxy_servers = {}
        if self._load_rc_func is None:
            return proxy_servers
        else:
            HTTP_PROXY = os.environ.get('HTTP_PROXY')
            HTTPS_PROXY = os.environ.get('HTTPS_PROXY')

            if HTTP_PROXY:
                proxy_servers['http'] = HTTP_PROXY

            if HTTPS_PROXY:
                proxy_servers['https'] = HTTPS_PROXY

            proxy_servers_conf = self._load_rc_func().get('proxy_servers', {})
            proxy_servers.update(proxy_servers_conf)

            return proxy_servers

    @staticmethod
    def _create_proxy(proxy_setting):
        """Create a Network proxy for the given proxy settings."""
        proxy = QNetworkProxy()
        proxy_scheme = proxy_setting['scheme']
        proxy_host = proxy_setting['host']
        proxy_port = proxy_setting['port']
        proxy_username = proxy_setting['username']
        proxy_password = proxy_setting['password']
        proxy_scheme_host = '{0}://{1}'.format(proxy_scheme, proxy_host)
        proxy.setType(QNetworkProxy.HttpProxy)

        if proxy_scheme_host:
            # proxy.setHostName(proxy_scheme_host)  # does not work with scheme
            proxy.setHostName(proxy_host)

        if proxy_port:
            proxy.setPort(proxy_port)

        if proxy_username:
            proxy.setUser(proxy_username)

        if proxy_password:
            proxy.setPassword(proxy_password)

        return proxy

    def queryProxy(self, query):
        """Override Qt method."""
        # Query is a QNetworkProxyQuery
        valid_proxies = []

        query_scheme = query.url().scheme()
        query_host = query.url().host()
        query_scheme_host = '{0}://{1}'.format(query_scheme, query_host)
        proxy_servers = process_proxy_servers(self.proxy_servers)
#        print(proxy_servers)

        if proxy_servers:
            for key in proxy_servers:
                proxy_settings = proxy_servers[key]

                if key == 'http' and query_scheme == 'http':
                    proxy = self._create_proxy(proxy_settings)
                    valid_proxies.append(proxy)
                elif key == 'https' and query_scheme == 'https':
                    proxy = self._create_proxy(proxy_settings)
                    valid_proxies.append(proxy)

                if key == query_scheme_host:
                    proxy = self._create_proxy(proxy_settings)
                    valid_proxies.append(proxy)
        else:
            valid_proxies.append(QNetworkProxy(QNetworkProxy.DefaultProxy))

#        print('factoy', query.url().toString())
#        print(valid_proxies)
#        for pr in valid_proxies:
#            user = pr.user()
#            password = pr.password()
#            host = pr.hostName()
#            port = pr.port()
#            print(query.url(), user, password, host, port)
#        print('\n')
        return valid_proxies


class DownloadWorker(QObject):
    """Qt Download worker."""

    # url, path
    sig_download_finished = Signal(str, str)

    # url, path, progress_size, total_size
    sig_download_progress = Signal(str, str, int, int)
    sig_finished = Signal(object, object, object)

    def __init__(self, url, path):
        """Qt Download worker."""
        super(DownloadWorker, self).__init__()
        self.url = url
        self.path = path
        self.finished = False

    def is_finished(self):
        """Return True if worker status is finished otherwise return False."""
        return self.finished


class _DownloadAPI(QObject):
    """Download API based on QNetworkAccessManager."""

    def __init__(self, chunk_size=1024, load_rc_func=None):
        """Download API based on QNetworkAccessManager."""
        super(_DownloadAPI, self).__init__()
        self._chunk_size = chunk_size
        self._head_requests = {}
        self._get_requests = {}
        self._paths = {}
        self._workers = {}

        self._load_rc_func = load_rc_func
        self._manager = QNetworkAccessManager(self)
        self._proxy_factory = NetworkProxyFactory(load_rc_func=load_rc_func)
        self._timer = QTimer()

        # Setup
        self._manager.setProxyFactory(self._proxy_factory)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._clean)

        # Signals
        self._manager.finished.connect(self._request_finished)
        self._manager.sslErrors.connect(self._handle_ssl_errors)
        self._manager.proxyAuthenticationRequired.connect(
            self._handle_proxy_auth)

    @staticmethod
    def _handle_ssl_errors(reply, errors):
        """Callback for ssl_errors."""
        logger.error(str(('SSL Errors', errors, reply)))

    @staticmethod
    def _handle_proxy_auth(proxy, authenticator):
        """Callback for ssl_errors."""
#        authenticator.setUser('1')`
#        authenticator.setPassword('1')
        logger.error(str(('Proxy authentication Error. '
                          'Enter credentials in condarc',
                          proxy,
                          authenticator)))

    def _clean(self):
        """Check for inactive workers and remove their references."""
        if self._workers:
            for url in self._workers.copy():
                w = self._workers[url]
                if w.is_finished():
                    self._workers.pop(url)
                    self._paths.pop(url)
                    if url in self._get_requests:
                        self._get_requests.pop(url)

        else:
            self._timer.stop()

    def _request_finished(self, reply):
        """Callback for download once the request has finished."""
        url = to_text_string(reply.url().toEncoded(), encoding='utf-8')

        if url in self._paths:
            path = self._paths[url]
        if url in self._workers:
            worker = self._workers[url]

        if url in self._head_requests:
            error = reply.error()
#            print(url, error)
            if error:
                logger.error(str(('Head Reply Error:', error)))
                worker.sig_download_finished.emit(url, path)
                worker.sig_finished.emit(worker, path, error)
                return

            self._head_requests.pop(url)
            start_download = not bool(error)
            header_pairs = reply.rawHeaderPairs()
            headers = {}

            for hp in header_pairs:
                headers[to_text_string(hp[0]).lower()] = to_text_string(hp[1])

            total_size = int(headers.get('content-length', 0))

            # Check if file exists
            if os.path.isfile(path):
                file_size = os.path.getsize(path)

                # Check if existing file matches size of requested file
                start_download = file_size != total_size

            if start_download:
                # File sizes dont match, hence download file
                qurl = QUrl(url)
                request = QNetworkRequest(qurl)
                self._get_requests[url] = request
                reply = self._manager.get(request)

                error = reply.error()
                if error:
                    logger.error(str(('Reply Error:', error)))

                reply.downloadProgress.connect(
                    lambda r, t, w=worker: self._progress(r, t, w))
            else:
                # File sizes match, dont download file or error?
                worker.finished = True
                worker.sig_download_finished.emit(url, path)
                worker.sig_finished.emit(worker, path, None)
        elif url in self._get_requests:
            data = reply.readAll()
            self._save(url, path, data)

    def _save(self, url, path, data):
        """Save `data` of downloaded `url` in `path`."""
        worker = self._workers[url]
        path = self._paths[url]

        if len(data):
            try:
                with open(path, 'wb') as f:
                    f.write(data)
            except Exception:
                logger.error((url, path))

        # Clean up
        worker.finished = True
        worker.sig_download_finished.emit(url, path)
        worker.sig_finished.emit(worker, path, None)
        self._get_requests.pop(url)
        self._workers.pop(url)
        self._paths.pop(url)

    @staticmethod
    def _progress(bytes_received, bytes_total, worker):
        """Return download progress."""
        worker.sig_download_progress.emit(
            worker.url, worker.path, bytes_received, bytes_total)

    def download(self, url, path):
        """Download url and save data to path."""
        # original_url = url
#        print(url)
        qurl = QUrl(url)
        url = to_text_string(qurl.toEncoded(), encoding='utf-8')

        logger.debug(str((url, path)))
        if url in self._workers:
            while not self._workers[url].finished:
                return self._workers[url]

        worker = DownloadWorker(url, path)

        # Check download folder exists
        folder = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(folder):
            os.makedirs(folder)

        request = QNetworkRequest(qurl)
        self._head_requests[url] = request
        self._paths[url] = path
        self._workers[url] = worker
        self._manager.head(request)
        self._timer.start()

        return worker

    def terminate(self):
        """Terminate all download workers and threads."""
        pass


class RequestsDownloadWorker(QObject):
    """Download Worker based on requests."""

    sig_finished = Signal(object, object, object)
    sig_download_finished = Signal(str, str)
    sig_download_progress = Signal(str, str, int, int)

    def __init__(self, method, args, kwargs):
        """Download Worker based on requests."""
        super(RequestsDownloadWorker, self).__init__()
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self._is_finished = False

    def is_finished(self):
        """Return True if worker status is finished otherwise return False."""
        return self._is_finished

    def start(self):
        """Start process worker for given method args and kwargs."""
        error = None
        output = None

        try:
            output = self.method(*self.args, **self.kwargs)
        except Exception as err:
            error = err
            logger.debug(str((self.method.__name__,
                              self.method.__module__,
                              error)))

        self.sig_finished.emit(self, output, error)
        self._is_finished = True


class _RequestsDownloadAPI(QObject):
    """Download API based on requests."""

    _sig_download_finished = Signal(str, str)
    _sig_download_progress = Signal(str, str, int, int)

    def __init__(self, load_rc_func=None):
        """Download API based on requests."""
        super(QObject, self).__init__()
        self._conda_api = CondaAPI()
        self._queue = deque()
        self._threads = []
        self._workers = []
        self._timer = QTimer()

        self._load_rc_func = load_rc_func
        self._chunk_size = 1024
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._clean)

    @property
    def proxy_servers(self):
        """Return the proxy servers available from the conda rc config file."""
        if self._load_rc_func is None:
            return {}
        else:
            return self._load_rc_func().get('proxy_servers', {})

    def _clean(self):
        """Check for inactive workers and remove their references."""
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
        """Start the next threaded worker in the queue."""
        if len(self._queue) == 1:
            thread = self._queue.popleft()
            thread.start()
            self._timer.start()

    def _create_worker(self, method, *args, **kwargs):
        """Create a new worker instance."""
        thread = QThread()
        worker = RequestsDownloadWorker(method, args, kwargs)
        worker.moveToThread(thread)
        worker.sig_finished.connect(self._start)
        self._sig_download_finished.connect(worker.sig_download_finished)
        self._sig_download_progress.connect(worker.sig_download_progress)
        worker.sig_finished.connect(thread.quit)
        thread.started.connect(worker.start)
        self._queue.append(thread)
        self._threads.append(thread)
        self._workers.append(worker)
        self._start()
        return worker

    def _download(self, url, path=None, force=False):
        """Callback for download."""
        if path is None:
            path = url.split('/')[-1]

        # Make dir if non existent
        folder = os.path.dirname(os.path.abspath(path))

        if not os.path.isdir(folder):
            os.makedirs(folder)

        # Start actual download
        try:
            r = requests.get(url, stream=True, proxies=self.proxy_servers)
        except Exception as error:
            logger.error(str(error))
            # Break if error found!
#            self._sig_download_finished.emit(url, path)
#            return path

        total_size = int(r.headers.get('Content-Length', 0))

        # Check if file exists
        if os.path.isfile(path) and not force:
            file_size = os.path.getsize(path)

            # Check if existing file matches size of requested file
            if file_size == total_size:
                self._sig_download_finished.emit(url, path)
                return path

        # File not found or file size did not match. Download file.
        progress_size = 0
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=self._chunk_size):
                if chunk:
                    f.write(chunk)
                    progress_size += len(chunk)
                    self._sig_download_progress.emit(url, path,
                                                     progress_size,
                                                     total_size)
            self._sig_download_finished.emit(url, path)

        return path

    def _is_valid_url(self, url):
        """Callback for is_valid_url."""
        try:
            r = requests.head(url, proxies=self.proxy_servers)
            value = r.status_code in [200]
        except Exception as error:
            logger.error(str(error))
            value = False

        return value

    def _is_valid_channel(self, channel,
                          conda_url='https://conda.anaconda.org'):
        """Callback for is_valid_channel."""
        if channel.startswith('https://') or channel.startswith('http://'):
            url = channel
        else:
            url = "{0}/{1}".format(conda_url, channel)

        if url[-1] == '/':
            url = url[:-1]

        plat = self._conda_api.get_platform()
        repodata_url = "{0}/{1}/{2}".format(url, plat, 'repodata.json')

        try:
            r = requests.head(repodata_url, proxies=self.proxy_servers)
            value = r.status_code in [200]
        except Exception as error:
            logger.error(str(error))
            value = False

        return value

    def _is_valid_api_url(self, url):
        """Callback for is_valid_api_url."""
        # Check response is a JSON with ok: 1
        data = {}
        try:
            r = requests.get(url, proxies=self.proxy_servers)
            content = to_text_string(r.content, encoding='utf-8')
            data = json.loads(content)
        except Exception as error:
            logger.error(str(error))

        return data.get('ok', 0) == 1

    # --- Public API
    # -------------------------------------------------------------------------
    def download(self, url, path=None, force=False):
        """Download file given by url and save it to path."""
        logger.debug(str((url, path, force)))
        method = self._download
        return self._create_worker(method, url, path=path, force=force)

    def terminate(self):
        """Terminate all workers and threads."""
        for t in self._threads:
            t.quit()
        self._thread = []
        self._workers = []

    def is_valid_url(self, url, non_blocking=True):
        """Check if url is valid."""
        logger.debug(str((url)))
        if non_blocking:
            method = self._is_valid_url
            return self._create_worker(method, url)
        else:
            return self._is_valid_url(url)

    def is_valid_api_url(self, url, non_blocking=True):
        """Check if anaconda api url is valid."""
        logger.debug(str((url)))
        if non_blocking:
            method = self._is_valid_api_url
            return self._create_worker(method, url)
        else:
            return self._is_valid_api_url(url=url)

    def is_valid_channel(self,
                         channel,
                         conda_url='https://conda.anaconda.org',
                         non_blocking=True):
        """Check if a conda channel is valid."""
        logger.debug(str((channel, conda_url)))
        if non_blocking:
            method = self._is_valid_channel
            return self._create_worker(method, channel, conda_url)
        else:
            return self._is_valid_channel(channel, conda_url=conda_url)

    def get_api_info(self, url):
        """Query anaconda api info."""
        data = {}
        try:
            r = requests.get(url, proxies=self.proxy_servers)
            content = to_text_string(r.content, encoding='utf-8')
            data = json.loads(content)
            if not data:
                data['api_url'] = url
            if 'conda_url' not in data:
                data['conda_url'] = 'https://conda.anaconda.org'
        except Exception as error:
            logger.error(str(error))

        return data


DOWNLOAD_API = None
REQUESTS_DOWNLOAD_API = None


def DownloadAPI(load_rc_func=None):
    """Downlaod API based on Qt."""
    global DOWNLOAD_API

    if DOWNLOAD_API is None:
        DOWNLOAD_API = _DownloadAPI(load_rc_func=load_rc_func)

    return DOWNLOAD_API


def RequestsDownloadAPI(load_rc_func=None):
    """Download API threaded worker based on requests."""
    global REQUESTS_DOWNLOAD_API

    if REQUESTS_DOWNLOAD_API is None:
        REQUESTS_DOWNLOAD_API = _RequestsDownloadAPI(load_rc_func=load_rc_func)

    return REQUESTS_DOWNLOAD_API


# --- Local testing
# -----------------------------------------------------------------------------
def ready_print(worker, output, error):  # pragma: no cover
    """Print worker output for tests."""
    print(worker, output, error)


def test():  # pragma: no cover
    """Main local test."""
    from anaconda_navigator.utils.qthelpers import qapplication
    urls = [
        'https://repo.continuum.io/pkgs/free/linux-64/repodata.json.bz2',
        'https://repo.continuum.io/pkgs/free/linux-64/repodata.json.bz2',
        'https://conda.anaconda.org/anaconda/linux-64/repodata.json.bz2',
        'https://conda.anaconda.org/asmeurer/linux-64/repodata.json.bz2',
        'https://conda.anaconda.org/conda-forge/linux-64/repodata.json.bz2',
            ]
    path = os.sep.join([os.path.expanduser('~'), 'testing-download'])
    app = qapplication()
    api = DownloadAPI()

    for i, url in enumerate(urls):
        filepath = os.path.join(path, str(i) + '.json.bz2')
        worker = api.download(url, filepath)
        worker.sig_finished.connect(ready_print)
        print('Downloading', url, filepath)

    path = os.sep.join([os.path.expanduser('~'), 'testing-download-requests'])
    api = RequestsDownloadAPI()
    urls += ['asdasdasdad']
    for i, url in enumerate(urls):
        worker = api.is_valid_url(url)
        worker.url = url
        worker.sig_finished.connect(ready_print)
        filepath = os.path.join(path, str(i) + '.json.bz2')
        worker = api.download(url, path=filepath, force=True)
        worker.sig_finished.connect(ready_print)

    api = RequestsDownloadAPI()
    print(api._is_valid_api_url('https://api.anaconda.org'))
    print(api._is_valid_api_url('https://conda.anaconda.org'))
    print(api._is_valid_channel('https://google.com'))
    print(api._is_valid_channel('https://conda.anaconda.org/continuumcrew'))
    print(api.get_api_info('https://api.anaconda.org'))
    sys.exit(app.exec_())


if __name__ == '__main__':  # pragma: no cover
    test()
