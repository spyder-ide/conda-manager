# -*- coding: utf-8 -*-
"""

"""

import os
import os.path as osp

from qtpy.QtCore import QByteArray, QObject, QUrl
from qtpy.QtNetwork import QNetworkAccessManager, QNetworkRequest

from ..utils.py3compat import to_text_string


# TODO: Change to use requests library instead of Qt ....

class DownloadManager(QObject):
    """Synchronous download manager.

    http://qt-project.org/doc/qt-4.8/network-downloadmanager-downloadmanager-cpp.html
    as inspiration.
    """
    def __init__(self, parent, on_finished_func, on_progress_func, save_path):
        super(DownloadManager, self).__init__(parent)
        self._parent = parent

        self._on_finished_func = on_finished_func
        self._on_progress_func = on_progress_func

        self._manager = QNetworkAccessManager(self)
        self._request = None
        self._reply = None
        self._queue = None         # [['filename', 'uri'], ...]
        self._url = None           # current url in process
        self._filename = None      # current filename in process
        self._save_path = None     # current defined save path
        self._error = None         # error number
        self._free = True          # lock process flag

        self.set_save_path(save_path)

    def _start_next_download(self):
        """ """
        if self._free:
            if len(self._queue) != 0:
                self._free = False
                self._filename, self._url = self._queue.pop(0)
                full_path = osp.join(self._save_path, self._filename)

                if osp.isfile(full_path):
                    # compare file versions by getting headers first
                    self._get(header_only=True)
                else:
                    # file does not exists, first download
                    self._get()
                # print(full_path)
            else:
                self._on_finished_func()

    def _get(self, header_only=False):
        """Download file specified by uri"""
        self._request = QNetworkRequest(QUrl(self._url))
        self._reply = None
        self._error = None

        if header_only:
            self._reply = self._manager.head(self._request)
            self._reply.finished.connect(self._on_downloaded_headers)
        else:
            self._reply = self._manager.get(self._request)
            self._reply.finished.connect(self._on_downloaded)

        self._reply.downloadProgress.connect(self._on_progress)

    def _on_downloaded_headers(self):
        """On header from uri downloaded"""
        # handle error for headers...
        error_code = self._reply.error()
        if error_code > 0:
            self._on_errors(error_code)
            return None

        fullpath = osp.join(self._save_path, self._filename)
        headers = {}
        data = self._reply.rawHeaderPairs()

        for d in data:
            if isinstance(d[0], QByteArray):
                d = [d[0].data(), d[1].data()]
            key = to_text_string(d[0], encoding='ascii')
            value = to_text_string(d[1], encoding='ascii')
            headers[key.lower()] = value

        if len(headers) != 0:
            header_filesize = int(headers['content-length'])
            local_filesize = int(osp.getsize(fullpath))

            if header_filesize == local_filesize:
                self._free = True
                self._start_next_download()
            else:
                self._get()

    def _on_downloaded(self):
        """On file downloaded"""
        # check if errors
        error_code = self._reply.error()
        if error_code > 0:
            self._on_errors(error_code)
            return None

        # process data if no errors
        data = self._reply.readAll()

        self._save_file(data)

    def _on_errors(self, e):
        """On download errors"""
        self._free = True  # otherwise update button cannot work!
        self._error = e
        self._on_finished_func()

    def _on_progress(self, downloaded_size, total_size):
        """On Partial progress"""
        self._on_progress_func([downloaded_size, total_size])

    def _save_file(self, data):
        """ """
        if not osp.isdir(self._save_path):
            os.mkdir(self._save_path)

        fullpath = osp.join(self._save_path, self._filename)

        if isinstance(data, QByteArray):
            data = data.data()

        with open(fullpath, 'wb') as f:
            f.write(data)

        self._free = True
        self._start_next_download()

    # public api
    # ----------
    def set_save_path(self, path):
        """ """
        self._save_path = path

    def set_queue(self, queue):
        """[['filename', 'uri'], ['filename', 'uri'], ...]"""
        self._queue = queue

    def get_errors(self):
        """ """
        return self._error

    def start_download(self):
        """ """
        self._start_next_download()

    def stop_download(self):
        """ """
        pass
