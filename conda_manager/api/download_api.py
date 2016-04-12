# -*- coding: utf-8 -*-

"""
Download API.
"""

# Standard library imports
from collections import deque
import json
import os
import sys

# Third part imports
from qtpy.QtCore import QByteArray, QObject, QTimer, QThread, QUrl, Signal
from qtpy.QtNetwork import QNetworkAccessManager, QNetworkRequest
import requests

# Local imports
from conda_manager.api.conda_api import CondaAPI
from conda_manager.utils.logs import logger


PY2 = sys.version[0] == '2'
PY3 = sys.version[0] == '3'


def to_binary_string(obj, encoding=None):
    """Convert `obj` to binary string (bytes in Python 3, str in Python 2)"""
    if PY2:
        # Python 2
        if encoding is None:
            return str(obj)
        else:
            return obj.encode(encoding)
    else:
        # Python 3
        return bytes(obj, 'utf-8' if encoding is None else encoding)


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


class DownloadWorker(QObject):
    # url, path
    sig_download_finished = Signal(str, str)
    # url, path, progress_size, total_size
    sig_download_progress = Signal(str, str, int, int)
    sig_finished = Signal(object, object, object)

    def __init__(self, url, path):
        super(DownloadWorker, self).__init__()
        self.url = url
        self.path = path
        self.finished = False

    def is_finished(self):
        return self.finished


class _DownloadAPI(QObject):
    """
    Download API based on QNetworkAccessManager
    """
    def __init__(self, chunk_size=1024):
        super(_DownloadAPI, self).__init__()
        self._chunk_size = chunk_size
        self._head_requests = {}
        self._get_requests = {}
        self._paths = {}
        self._workers = {}

        self._manager = QNetworkAccessManager(self)
        self._timer = QTimer()

        # Setup
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._clean)

        # Signals
        self._manager.finished.connect(self._request_finished)
        self._manager.sslErrors.connect(self._handle_ssl_errors)

    def _handle_ssl_errors(self, reply, errors):
        logger.error(str(('SSL Errors', errors)))

    def _clean(self):
        """
        Periodically check for inactive workers and remove their references.
        """
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
        url = to_text_string(reply.url().toEncoded(), encoding='utf-8')

        if url in self._paths:
            path = self._paths[url]
        if url in self._workers:
            worker = self._workers[url]

        if url in self._head_requests:
            self._head_requests.pop(url)
            start_download = True
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
                # File sizes match, dont download file
                worker.finished = True
                worker.sig_download_finished.emit(url, path)
                worker.sig_finished.emit(worker, path, None)
        elif url in self._get_requests:
            data = reply.readAll()
            self._save(url, path, data)

    def _save(self, url, path, data):
        """
        """
        worker = self._workers[url]
        path = self._paths[url]

        if len(data):
            with open(path, 'wb') as f:
                f.write(data)

        # Clean up
        worker.finished = True
        worker.sig_download_finished.emit(url, path)
        worker.sig_finished.emit(worker, path, None)
        self._get_requests.pop(url)
        self._workers.pop(url)
        self._paths.pop(url)

    def _progress(self, bytes_received, bytes_total, worker):
        """
        """
        worker.sig_download_progress.emit(
            worker.url, worker.path, bytes_received, bytes_total)

    def download(self, url, path):
        """
        """
        # original_url = url
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
        pass


class RequestsDownloadWorker(QObject):
    """
    """
    sig_finished = Signal(object, object, object)
    sig_download_finished = Signal(str, str)
    sig_download_progress = Signal(str, str, int, int)

    def __init__(self, method, args, kwargs):
        super(RequestsDownloadWorker, self).__init__()
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self._is_finished = False

    def is_finished(self):
        """
        """
        return self._is_finished

    def start(self):
        """
        """
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
    """
    """
    _sig_download_finished = Signal(str, str)
    _sig_download_progress = Signal(str, str, int, int)

    def __init__(self):
        super(QObject, self).__init__()
        self._conda_api = CondaAPI()
        self._queue = deque()
        self._threads = []
        self._workers = []
        self._timer = QTimer()

        self._chunk_size = 1024
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
        """
        # FIXME: this might be heavy...
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
        """
        """
        if path is None:
            path = url.split('/')[-1]

        # Make dir if non existent
        folder = os.path.dirname(os.path.abspath(path))

        if not os.path.isdir(folder):
            os.makedirs(folder)

        # Start actual download
        try:
            r = requests.get(url, stream=True)
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
        try:
            r = requests.head(url)
            value = r.status_code in [200]
        except Exception as error:
            logger.error(str(error))
            value = False

        return value

    def _is_valid_channel(self, channel,
                          conda_url='https://conda.anaconda.org'):
        """
        """
        if channel.startswith('https://') or channel.startswith('http://'):
            url = channel
        else:
            url = "{0}/{1}".format(conda_url, channel)

        if url[-1] == '/':
            url = url[:-1]

        plat = self._conda_api.get_platform()
        repodata_url = "{0}/{1}/{2}".format(url, plat, 'repodata.json')

        try:
            r = requests.head(repodata_url)
            value = r.status_code in [200]
        except Exception as error:
            logger.error(str(error))
            value = False

        return value

    def _is_valid_api_url(self, url):
        """
        """
        # Check response is a JSON with ok: 1
        data = {}
        try:
            r = requests.get(url)
            content = to_text_string(r.content, encoding='utf-8')
            data = json.loads(content)
        except Exception as error:
            logger.error(str(error))

        return data.get('ok', 0) == 1

    def download(self, url, path=None, force=False):
        logger.debug(str((url, path, force)))
        method = self._download
        return self._create_worker(method, url, path=path, force=force)

    def terminate(self):
        for t in self._threads:
            t.quit()
        self._thread = []
        self._workers = []

    def is_valid_url(self, url, non_blocking=True):
        logger.debug(str((url)))
        if non_blocking:
            method = self._is_valid_url
            return self._create_worker(method, url)
        else:
            return self._is_valid_url(url)

    def is_valid_api_url(self, url, non_blocking=True):
        logger.debug(str((url)))
        if non_blocking:
            method = self._is_valid_api_url
            return self._create_worker(method, url)
        else:
            return self._is_valid_api_url(url=url)

    def is_valid_channel(self, channel,
                         conda_url='https://conda.anaconda.org',
                         non_blocking=True):
        logger.debug(str((channel, conda_url)))
        if non_blocking:
            method = self._is_valid_channel
            return self._create_worker(method, channel, conda_url)
        else:
            return self._is_valid_channel(channel, conda_url=conda_url)


DOWNLOAD_API = None
REQUESTS_DOWNLOAD_API = None


def DownloadAPI():
    global DOWNLOAD_API

    if DOWNLOAD_API is None:
        DOWNLOAD_API = _DownloadAPI()

    return DOWNLOAD_API


def RequestsDownloadAPI():
    global REQUESTS_DOWNLOAD_API

    if REQUESTS_DOWNLOAD_API is None:
        REQUESTS_DOWNLOAD_API = _RequestsDownloadAPI()

    return REQUESTS_DOWNLOAD_API


def ready_print(worker, output, error):
    print(worker.method.__name__, output, error)


def test():
    from conda_manager.utils.qthelpers import qapplication
    urls = ['http://repo.continuum.io/pkgs/free/linux-64/repodata.json.bz2',
            'https://conda.anaconda.org/anaconda/linux-64/repodata.json.bz2',
            'https://conda.anaconda.org/asmeurer/linux-64/repodata.json.bz2',
            ]
    path = os.sep.join([os.path.expanduser('~'), 'testing-download'])
    app = qapplication()
    api = DownloadAPI()

    for i, url in enumerate(urls):
        filepath = os.path.join(path, str(i) + '.json.bz2')
        api.download(url, filepath)
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
    app.exec_()


if __name__ == '__main__':
    test()
