"""
"""

# Standard library imports
import bz2
import json
import os

# Third party imports
from qtpy.QtCore import QObject, Signal

# Local imports
from conda_manager.api.conda_api import CondaAPI
from conda_manager.api.client_api import ClientAPI
from conda_manager.api.download_api import DownloadAPI, RequestsDownloadAPI
from conda_manager.utils.py3compat import to_text_string


class _AnacondaAPI(QObject):
    """
    """
    sig_channels_updated = Signal(object)
    sig_repodata_updated = Signal(object)

    def __init__(self):
        """
        """
        super(_AnacondaAPI, self).__init__()

        # API's
        self._conda_api = CondaAPI()
        self._client_api = ClientAPI()
        self._download_api = DownloadAPI()
        self._requests_download_api = RequestsDownloadAPI()
        self.ROOT_PREFIX = self._conda_api.ROOT_PREFIX

        # Vars
        self._checking_repos = None
        self._data_directory = None
        self._files_downloaded = None
        self._repodata_files = None
        self._valid_repos = None

        # Expose some methods for convenient access. Method return a worker
        self.conda_create = self._conda_api.create
        self.conda_install = self._conda_api.install
        self.conda_remove = self._conda_api.remove
        self.conda_dependencies = self._conda_api.dependencies
        self.conda_terminate = self._conda_api.terminate_all_processes
        self.get_condarc_channels = self._conda_api.get_condarc_channels
        self.pip_list = self._conda_api.pip_list
        self.pip_remove = self._conda_api.pip_remove
        self.linked = self._conda_api.linked
        self.environment_exists = self._conda_api.environment_exists
        self.get_envs = self._conda_api.get_envs

        # These methods return a worker
        self.download_async = self._download_api.download
        self.download = self._requests_download_api.download
        self.is_valid_url = self._requests_download_api.is_valid_url

        # These client methods return a worker
        self.client_login = self._client_api.login
        self.client_logout = self._client_api.logout
        self.client_load_repodata = self._client_api.load_repodata
        self.client_prepare_model_data = self._client_api.prepare_model_data

    # --- Helper methods
    # -------------------------------------------------------------------------
    def _set_repo_urls_from_channels(self, channels):
        """
        Convert a channel into a normalized repo name including the local
        platform.

        Channels are assumed in normalized url form.
        """
        repos = []
        sys_platform = self._conda_api.get_platform()

        for channel in channels:
            url = '{0}/{1}/repodata.json.bz2'.format(channel, sys_platform)
            repos.append(url)

        return repos

    def _check_repos(self, repos):
        """
        Check if repodata urls are valid.
        """
        self._checking_repos = []
        self._valid_repos = []

        for repo in repos:
            worker = self._requests_download_api.is_valid_url(repo)
            worker.sig_finished.connect(self._repos_checked)
            worker.repo = repo
            self._checking_repos.append(repo)

    def _repos_checked(self, worker, output, error):
        """
        """
        self._checking_repos.remove(worker.repo)

        if output:
            self._valid_repos.append(worker.repo)

        if len(self._checking_repos) == 0:
            self._download_repodata(self._valid_repos)

    def _repo_url_to_path(self, repo):
        """
        Convert a `repo` url to a file path for local storage.
        """
        repo = repo.replace('http://', '')
        repo = repo.replace('https://', '')
        repo = repo.replace('/', '_')

        return os.sep.join([self._data_directory, repo])

    def _download_repodata(self, checked_repos):
        """
        """
        self._files_downloaded = []
        self._repodata_files = []

        for repo in checked_repos:
            path = self._repo_url_to_path(repo)
            self._files_downloaded.append(path)
            self._repodata_files.append(path)
            worker = self.download_async(repo, path)
            worker.sig_download_finished.connect(self._repodata_downloaded)

    def _repodata_downloaded(self, url, path):
        """
        """
        if path in self._files_downloaded:
            self._files_downloaded.remove(path)

        if len(self._files_downloaded) == 0:
            self.sig_repodata_updated.emit(self._repodata_files)

#    def _load_repodata_packages(self, paths, compressed=True):
#        """
#        Load repodata.json local files located at `paths`.
#        """
#        all_packages = {}
#        for path in paths:
#            if os.path.isfile(path):
#                with open(path, 'rb') as f:
#                    raw_data = f.read()
#
#                if compressed:
#                    data = to_text_string(bz2.decompress(raw_data))
#                else:
#                    data = to_text_string(raw_data)
#
#                try:
#                    metadata = json.loads(data)
#                    packages = metadata['packages']
#                    all_packages.update(packages)
#                except ValueError:
#                    continue
#
#        return all_packages
#
#    def _get_package_apps(self, packages):
#        """
#        Get conda packages metadata of packages listed as applications.
#        """
#        apps = {}
#        for key in packages:
#            package = packages[key]
#            is_app = package.get('type', None) == 'app'
#
#            if is_app:
#                apps[key] = package
#
#        return apps
#
#    def _clean_package_apps(self, package_apps):
#        """
#        Transform the package metadata of applications found into a common
#        format. This format is similar to the one returned by anaconda.org
#        """
#        names = {}
#        for package in package_apps:
#            meta = package_apps[package]
#            name, v, b = tuple(package.rsplit('-', 2))
#            version = meta.get('version')
#            app_entry = package_apps[package].get('app_entry', '')
#            app_summary = package_apps[package].get('summary', '')
#            app_type = package_apps[package].get('app_type', '')
#
#            if name in names:
#                names[name]['name'] = name
#                names[name]['versions'].append(version)
#                names[name]['app_entry'][version] = app_entry
#                names[name]['app_summary'][version] = app_summary
#                names[name]['app_type'][version] = app_type
#            else:
#                names[name] = {'versions': [version],
#                               'app_entry': {version: app_entry},
#                               'app_summary': {version: app_summary},
#                               'app_type': {version: app_type},
#                               }
#        for name in names:
#            app = names[name]
#            versions = app['versions']
#            versions = list(set(versions))
#            versions = sorted(versions, reverse=True)
#            app['versions'] = versions
#        return names

    # --- Public API
    # -------------------------------------------------------------------------
    def update_repodata(self, data_directory, channels=None):
        """
        Update repodata defined `channels`. If no channels are provided,
        the default channels are used.

        When finished, this method emits the `sig_repodata_updated` signal
        with a list of the downloaded files.
        """
        self._data_directory = data_directory

        if channels is None:
            channels = self._conda_api.get_condarc_channels()

        repodata_urls = self._set_repo_urls_from_channels(channels)
        self._check_repos(repodata_urls)

    def update_metadata(self, data_directory):
        """
        Update the metadata available for packages in repo.continuum.io.

        Returns a download worker.
        """
        metadata_url = 'http://repo.continuum.io/pkgs/metadata.json'
        filepath = os.sep.join([data_directory, 'metadata.json'])
        return self._download_api.download(metadata_url, filepath)


ANACONDA_API = None


def AnacondaAPI():
    global ANACONDA_API

    if ANACONDA_API is None:
        ANACONDA_API = _AnacondaAPI()

    return ANACONDA_API


def finished(worker, output, error):
    print(worker, output, error)


def download_finished(url, path):
    print(url, path)


def repodata_updated(repos):
    print(repos)


def test():
    from conda_manager.utils.qthelpers import qapplication
    app = qapplication()
    api = AnacondaAPI()
    api.sig_repodata_updated.connect(repodata_updated)
    data_directory = '/home/goanpeca/temp-channels-folder'
    worker = api.update_metadata(data_directory)
    worker.sig_download_finished.connect(download_finished)
    api.update_repodata(data_directory)
    app.exec_()


if __name__ == '__main__':
    test()
