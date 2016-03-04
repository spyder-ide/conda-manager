# -*- coding: utf-8 -*-

"""
Download API.
"""

# Standard library imports
from collections import deque
import os
import sys

# Third part imports
from qtpy.QtCore import QObject, QTimer, QThread, QUrl, Signal, QByteArray
from qtpy.QtNetwork import QNetworkAccessManager, QNetworkRequest
import requests

# Local imports
from conda_manager.utils.logs import logger

PY2 = sys.version[0] == '2'
PY3 = sys.version[0] == '3'


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
    sig_download_finished = Signal(str, str)            # url, path
    sig_download_progress = Signal(str, str, int, int)  # url, path, progress_size, total_size
    sig_finished = Signal(object, object, object)

    def __init__(self, url, path):
        super(DownloadWorker, self).__init__()
        self.url = url
        self.path = path


class _DownloadAPI(QObject):
    """
    Download API based on QNetworkAccessManager
    """
    def __init__(self, chunk_size=1024):
        super(_DownloadAPI, self).__init__()
        self._chunk_size = chunk_size
        self._head_requests = {}
        self._get_requests = {}
        self._data = {}
        self._workers = {}
        self._old_requests = []

        self._manager = QNetworkAccessManager(self)

        self._manager.finished.connect(self._request_finished)

    def _request_finished(self, reply):
        """
        """
        url = reply.url().toString()
        path = self._data[url]
        worker = self._workers[url]

        if url in self._head_requests:
            req = self._head_requests.pop(url)
            self._old_requests.append(req)
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
                qurl = QUrl(url)
                request = QNetworkRequest(qurl)
                self._get_requests[url] = request
                reply = self._manager.get(request)
                reply.downloadProgress.connect(
                    lambda r, t, w=worker: self._progress(r, t, w))
            else:
                worker.sig_download_finished.emit(url, path)
                worker.sig_finished.emit(worker, path, None)
                self._workers.pop(url)
        elif url in self._get_requests:
            data = reply.readAll()
            self._save(url, path, data)

    def _save(self, url, path, data):
        """
        """
        worker = self._workers[url]
        path = self._data[url]
        with open(path, 'wb') as f:
            f.write(data)

        # Clean up
        worker.sig_download_finished.emit(url, path)
        worker.sig_finished.emit(worker, path, None)
        req = self._get_requests.pop(url)
        self._old_requests.append(req)
        self._workers.pop(url)
        self._data.pop(url)

    def _progress(self, bytes_received, bytes_total, worker):
        """
        """
        worker.sig_download_progress.emit(
            worker.url, worker.path, bytes_received, bytes_total)

    def download(self, url, path):
        """
        """
        logger.debug(str((url, path)))
        worker = DownloadWorker(url, path)
        if url in self._workers:
            return worker

        # Check download folder exists
        folder = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(folder):
            os.makedirs(folder)

        qurl = QUrl(url)
        request = QNetworkRequest(qurl)
        self._head_requests[url] = request
        self._data[url] = path
        self._workers[url] = worker
        self._manager.head(request)

        return worker


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
        error, output = None, None
        try:
            output = self.method(*self.args, **self.kwargs)
        except Exception as error:
            logger.debug(str((self.method.__name__,
                              self.method.__module__,
                              error)))

        self.sig_finished.emit(self, output, error)
#        print('emited', self.method.__name__)
        self._is_finished = True


class _RequestsDownloadAPI(QObject):
    """
    """
    _sig_download_finished = Signal(str, str)
    _sig_download_progress = Signal(str, str, int, int)

    def __init__(self):
        super(QObject, self).__init__()
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

    def download(self, url, path=None, force=False):
        logger.debug(str((url, path, force)))
        method = self._download
        return self._create_worker(method, url, path=path, force=force)

    def terminate(self):
        for t in self._threads:
            t.quit()
        self._thread = []
        self._workers = []

    def is_valid_url(self, url):
        logger.debug(str((url)))
        method = self._is_valid_url
        return self._create_worker(method, url)


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

    app.exec_()


if __name__ == '__main__':
    test()
