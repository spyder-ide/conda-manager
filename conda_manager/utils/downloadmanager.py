# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""

"""

# Standard library imports
import bz2
import io
import multiprocessing
import os
import sys

# Third party imports
from qtpy.QtCore import Signal, QObject, QThread, QTimer
from qtpy.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
import requests


def human_bytes(n):
    """
    Return the number of bytes n in more human readable form.
    """
    if n < 1024:
        return '%d B' % n
    k = n/1024
    if k < 1024:
        return '%d KB' % round(k)
    m = k/1024
    if m < 1024:
        return '%.1f MB' % m
    g = m/1024
    return '%.2f GB' % g


# --- Async worker
# -----------------------------------------------------------------------------
def aget(item):
    """
    """
    path = item['path']
    url = item['url']
    request = requests.get(url, stream=True)
    content_length = int(request.headers.get('content-length', -1))
    con = aget.total_queue.get()
    aget.total_queue.put(content_length + con)
    aget.count.put(0)
    stream = io.BytesIO()

    for i, chunk in enumerate(request.iter_content(chunk_size=1024)):
        if chunk:
            prog = aget.queue.get()
            progress = len(chunk) + prog
            aget.queue.put(progress)
            stream.write(chunk)

    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))

    with open(path, 'wb') as f:
        f.write(stream.getvalue())


def pool_init(queue, total_queue, count):
    """
    """
    # see http://stackoverflow.com/a/3843313/852994
    aget.queue = queue
    aget.total_queue = total_queue
    aget.count = count


class AsyncRequestsWorker(QObject):
    """
    Asynchronous download worker using requests.
    """
    sig_finished = Signal()
    sig_partial = Signal(object, object)

    def __init__(self, parent, queue, save_path):
        QObject.__init__(self)
        self._parent = parent
        self._queue = queue
        self._save_path = save_path
        self._url = None             # current url in process
        self._filename = None        # current filename in process
        self._error = None           # error number
        self._free = True            # lock process flag
        self._partial_queue = multiprocessing.Queue()
        self._partial_queue.put(0)
        self._total_queue = multiprocessing.Queue()
        self._total_queue.put(0)
        self._count = multiprocessing.Queue()
        cpu = multiprocessing.cpu_count()
        self._pool = multiprocessing.Pool(processes=cpu,
                                          initializer=pool_init,
                                          initargs=(self._partial_queue,
                                                    self._total_queue,
                                                    self._count))
        self._timer = QTimer()
        self._timer.timeout.connect(self._get_queue_messages)
        self._timer.start(100)
        self._total = 0
        self._partial = 0

    def _get_queue_messages(self):
        self._partial = self._partial_queue.get()
        self._total = self._total_queue.get()

        self.sig_partial.emit(self._partial, self._total)

        self._partial_queue.put(self._partial)
        self._total_queue.put(self._total)

        if (self._partial == self._total and
                self._total_queue.qsize() == len(self._queue)):
            self._timer.stop()
            self.sig_finished.emit()

    def start(self):
        items = []
        for q in self._queue:
            dic = {'path': os.path.join(self._save_path, q[0]),
                   'url': q[1],
                   }
            items.append(dic)
        self._pool.map(aget, items)


# --- Sync worker
# -----------------------------------------------------------------------------
class RequestsWorker(QObject):
    """
    Synchronous download worker using requests.
    """
    sig_finished = Signal()
    sig_partial = Signal(object, object)

    def __init__(self, parent, queue, save_path, check_size):
        QObject.__init__(self)
        self._parent = parent
        self._queue = queue
        self._save_path = save_path
        self._url = None             # current url in process
        self._filename = None        # current filename in process
        self._error = None           # error number
        self._free = True            # lock process flag
        self._check_size = check_size

    def start(self, i=None):
        """ """
        if self._free:
            if self._queue and len(self._queue) != 0:
                self._free = False
                self._filename, self._url = self._queue.pop(0)
                full_path = os.path.join(self._save_path, self._filename)

                if os.path.isfile(full_path) and self._check_size:
                    # Compare file versions by getting headers first
                    self._get_headers(full_path)
                elif os.path.isfile(full_path) and not self._check_size:
                    # If a file matches the name dont download anything
                    self._free = True
                    self.start()
                else:
                    # File does not exists, first download
                    self._get(full_path)
            else:
                self.sig_finished.emit()
        else:
            self.start()

    def _get_headers(self, path):
        """
        Download file header specified by uri.
        """
        self._free = False
        self._reply = None
        self._error = None
        fullpath = os.path.join(self._save_path, self._filename)

        request = requests.get(self._url, stream=True)
        header_filesize = int(request.headers.get('Content-Length', -1))
        local_filesize = int(os.path.getsize(fullpath))

        if local_filesize != header_filesize:
            self._get(path, request=request)
        else:
            self.sig_partial.emit(100, 100)
            self._free = True
            self.start()

    def _get(self, path, request=None):
        """
        Download file specified by uri.
        """
        self._free = False
        if request is None:
            request = requests.get(self._url, stream=True)

        content_length = int(request.headers.get('Content-Length', -1))
        stream = io.BytesIO()
        for i, chunk in enumerate(request.iter_content(chunk_size=1024)):
            if chunk:
                progress = i*1024 + len(chunk)
                if content_length == -1:
                    progress = -1
                self.sig_partial.emit(progress, content_length)
                stream.write(chunk)

        if path.endswith('.bz2'):
            raw = stream.getvalue()

            if not os.path.isdir(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            with open(path, 'wb') as f:
                f.write(raw)

            path = path.replace('.bz2', '')
            data = bz2.decompress(raw)
        else:
            data = stream.getvalue()

        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        with open(path, 'wb') as f:
            f.write(data)

        self._free = True
        self.start()


class RequestsDownloadManager(QObject):
    """Synchronous download manager using requests.

    Note: there is a QNetworkManager, but ssl seemed to be absent on some
    Qt versions, so the requests download manager is prefered.
    """
    sig_partial = Signal(object, object)
    sig_finished = Signal()

    def __init__(self, parent, save_path, async=False, check_size=True):
        super(RequestsDownloadManager, self).__init__(parent)
        self._parent = parent
        self._queue = []           # [['filename', 'uri'], ...]
        self._save_path = save_path  # current defined save path
        self._worker = None          # requests worker
        self._thread = QThread(self)
        self._async = async
        self._check_size = check_size

        # Make dir if not existing
        if not os.path.isdir(save_path):
            os.makedirs(save_path)

    def _setup(self):
        self._thread.terminate()
        self._thread = QThread(self)

        if self._async:
            self._worker = AsyncRequestsWorker(self, self._queue,
                                               self._save_path)
        else:
            self._worker = RequestsWorker(self,
                                          self._queue,
                                          self._save_path,
                                          self._check_size)

        self._worker.sig_partial.connect(self.sig_partial)
        self._worker.sig_finished.connect(self.sig_finished)
        self._worker.sig_finished.connect(self._thread.quit)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)

    # Public api
    # ----------
    def set_check_size(self, value):
        """ """
        self._check_size = value

    def set_save_path(self, path):
        """ """
        self._save_path = path

    def set_queue(self, queue):
        """[['filename', 'uri'], ['filename', 'uri'], ...]"""
        self._queue = queue
        self._setup()

    def get_errors(self):
        """ """
        return None
#        return self._worker._error

    def start_download(self):
        """ """
        self._thread.start()

    def stop_download(self):
        """ """
        self._thread.terminate()


class TestWidget(QWidget):
    def __init__(self):
        super(TestWidget, self).__init__()
        self.rdm = RequestsDownloadManager(None, '/home/goanpeca/Desktop/',
                                           async=False, check_size=False)
        self.button = QPushButton('Download')
        layout = QVBoxLayout()
        layout.addWidget(self.button)
        self.setLayout(layout)
        self.button.clicked.connect(self.download)
        self.button.clicked.connect(lambda: self.button.setEnabled(False))
        self.rdm.sig_finished.connect(lambda: self.button.setEnabled(True))

    def download(self):
        queue = [
            ['anaconda.json.bz2',
             'https://conda.anaconda.org/anaconda/linux-64/repodata.json.bz2'],
            ['asmeurer.json.bz2',
             'https://conda.anaconda.org/anaconda/linux-64/repodata.json.bz2'],
            ['boob.json.bz2',
             'https://conda.anaconda.org/anaconda/linux-64/repodata.json.bz2'],
            ['boob1.json.bz2',
             'https://conda.anaconda.org/anaconda/linux-64/repodata.json.bz2'],
            ['boob2.json.bz2',
             'https://conda.anaconda.org/anaconda/linux-64/repodata.json.bz2'],
            ['boob3.json.bz2',
             'https://conda.anaconda.org/anaconda/linux-64/repodata.json.bz2'],
            ]
        self.rdm.set_queue(queue)
        self.rdm.start_download()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = TestWidget()
    w.show()
    sys.exit(app.exec_())
