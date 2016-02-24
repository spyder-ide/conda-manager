"""
"""

# Standard library imports
import os
import tempfile

# Third party imports
from qtpy.QtCore import QObject, Signal

# Local imports
from conda_manager.api.conda_api import CondaAPI
from conda_manager.api.client_api import ClientAPI
from conda_manager.api.download_api import DownloadAPI, RequestsDownloadAPI


class _ManagerAPI(QObject):
    """
    """
    sig_repodata_updated = Signal(object)
    sig_repodata_errored = Signal()

    def __init__(self):
        """
        """
        super(_ManagerAPI, self).__init__()

        # API's
        self._client_api = ClientAPI()
        self._conda_api = CondaAPI()
        self._download_api = DownloadAPI()
        self._requests_download_api = RequestsDownloadAPI()
        self.ROOT_PREFIX = self._conda_api.ROOT_PREFIX

        # Vars
        self._checking_repos = None
        self._data_directory = None
        self._files_downloaded = None
        self._repodata_files = None
        self._valid_repos = None

        # Expose some methods for convenient access. Methods return a worker
        self.conda_create = self._conda_api.create
        self.conda_dependencies = self._conda_api.dependencies
        self.conda_get_condarc_channels = self._conda_api.get_condarc_channels
        self.conda_install = self._conda_api.install
        self.conda_remove = self._conda_api.remove
        self.conda_terminate = self._conda_api.terminate_all_processes
        self.pip_list = self._conda_api.pip_list
        self.pip_remove = self._conda_api.pip_remove

        # No workers are returned for these methods
        self.conda_environment_exists = self._conda_api.environment_exists
        self.conda_get_envs = self._conda_api.get_envs
        self.conda_linked = self._conda_api.linked
        self.conda_get_prefix_envname = self._conda_api.get_prefix_envname
        self.conda_package_version = self._conda_api.package_version

        # These download methods return a worker
        self.download = self._requests_download_api.download
        self.download_async = self._download_api.download
        self.download_is_valid_url = self._requests_download_api.is_valid_url

        # These client methods return a worker
        self.client_login = self._client_api.login
        self.client_logout = self._client_api.logout
        self.client_load_repodata = self._client_api.load_repodata
        self.client_prepare_packages_data = self._client_api.prepare_model_data
        self.client_set_domain = self._client_api.set_domain

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
            worker = self.download_is_valid_url(repo)
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

    # --- Public API
    # -------------------------------------------------------------------------
    def repodata_files(self, data_directory, channels=None):
        """
        Return the repodata paths based on `channels` and the `data_directory`.

        There is no check for validity here.
        """
        if channels is None:
            channels = self.conda_get_condarc_channels()

        repodata_urls = self._set_repo_urls_from_channels(channels)

        repopaths = []

        for repourl in repodata_urls:
            fullpath = os.sep.join([data_directory,
                                    self._repo_url_to_path(repourl)])
            repopaths.append(fullpath)

        return repopaths

    def set_data_directory(self, data_directory):
        """
        Set the directory where repodata and metadata are stored.
        """
        self._data_directory = data_directory

    def update_repodata(self, channels=None):
        """
        Update repodata defined `channels`. If no channels are provided,
        the default channels are used.

        When finished, this method emits the `sig_repodata_updated` signal
        with a list of the downloaded files.
        """
        if channels is None:
            channels = self.conda_get_condarc_channels()

        repodata_urls = self._set_repo_urls_from_channels(channels)
        self._check_repos(repodata_urls)

    def update_metadata(self):
        """
        Update the metadata available for packages in repo.continuum.io.

        Returns a download worker.
        """
        if self._data_directory is None:
            raise Exception('Need to call `api.set_data_directory` first.')

        metadata_url = 'http://repo.continuum.io/pkgs/metadata.json'
        filepath = os.sep.join([self._data_directory, 'metadata.json'])
        worker = self.download_async(metadata_url, filepath)
        return worker


MANAGER_API = None


def ManagerAPI():
    global MANAGER_API

    if MANAGER_API is None:
        MANAGER_API = _ManagerAPI()

    return MANAGER_API


def finished(worker, output, error):
    print(worker, output, error)


def download_finished(url, path):
    print(url, path)


def repodata_updated(repos):
    print(repos)


def test():
    from conda_manager.utils.qthelpers import qapplication
    app = qapplication()
    api = ManagerAPI()
    api.sig_repodata_updated.connect(repodata_updated)
    data_directory = tempfile.mkdtemp()
    worker = api.update_metadata(data_directory)
    worker.sig_download_finished.connect(download_finished)
    api.update_repodata(data_directory)
    app.exec_()


if __name__ == '__main__':
    test()
