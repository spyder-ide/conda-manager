# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright © 2015- The Spyder Development Team
# Copyright © 2014-2015 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License
# -----------------------------------------------------------------------------
"""API for using the api (anaconda-client, downloads and conda)."""

# Standard library imports
import json
import os
import tempfile

# Third party imports
from qtpy.QtCore import QObject, Signal

# Local imports
from conda_manager.api.client_api import ClientAPI
from conda_manager.api.conda_api import CondaAPI
from conda_manager.api.download_api import DownloadAPI, RequestsDownloadAPI


class _ManagerAPI(QObject):
    """Anaconda Manager API process worker."""

    sig_repodata_updated = Signal(object)
    sig_repodata_errored = Signal()

    def __init__(self):
        """Anaconda Manager API process worker."""
        super(_ManagerAPI, self).__init__()

        # API's
        self._conda_api = CondaAPI()
        self._client_api = ClientAPI()
        self._download_api = DownloadAPI(load_rc_func=self._conda_api.load_rc)
        self._requests_download_api = RequestsDownloadAPI(
            load_rc_func=self._conda_api.load_rc)
        self.ROOT_PREFIX = self._conda_api.ROOT_PREFIX

        # Vars
        self._checking_repos = None
        self._data_directory = None
        self._files_downloaded = None
        self._repodata_files = None
        self._valid_repos = None

        # Expose some methods for convenient access. Methods return a worker
        self.conda_create = self._conda_api.create
        self.conda_create_yaml = self._conda_api.create_from_yaml
        self.conda_clone = self._conda_api.clone_environment
        self.conda_dependencies = self._conda_api.dependencies
        self.conda_get_condarc_channels = self._conda_api.get_condarc_channels
        self.conda_install = self._conda_api.install
        self.conda_remove = self._conda_api.remove
        self.conda_terminate = self._conda_api.terminate_all_processes
        self.conda_config_add = self._conda_api.config_add
        self.conda_config_remove = self._conda_api.config_remove
        self.pip_list = self._conda_api.pip_list
        self.pip_remove = self._conda_api.pip_remove

        # No workers are returned for these methods
        self.conda_clear_lock = self._conda_api.clear_lock
        self.conda_environment_exists = self._conda_api.environment_exists
        self.conda_get_envs = self._conda_api.get_envs
        self.conda_linked = self._conda_api.linked
        self.conda_get_prefix_envname = self._conda_api.get_prefix_envname
        self.conda_package_version = self._conda_api.package_version
        self.conda_platform = self._conda_api.get_platform

        # These download methods return a worker
        get_api_info = self._requests_download_api.get_api_info
        is_valid_url = self._requests_download_api.is_valid_api_url
        is_valid_channel = self._requests_download_api.is_valid_channel
        terminate = self._requests_download_api.terminate
        self.download_requests = self._requests_download_api.download
        self.download_async = self._download_api.download
        self.download_async_terminate = self._download_api.terminate
        self.download_is_valid_url = self._requests_download_api.is_valid_url
        self.download_is_valid_api_url = is_valid_url
        self.download_get_api_info = lambda: get_api_info(
            self._client_api.get_api_url())
        self.download_is_valid_channel = is_valid_channel
        self.download_requests_terminate = terminate

        # These client methods return a worker
        self.client_store_token = self._client_api.store_token
        self.client_remove_token = self._client_api.remove_token
        self.client_login = self._client_api.login
        self.client_logout = self._client_api.logout
        self.client_load_repodata = self._client_api.load_repodata
        self.client_prepare_packages_data = self._client_api.prepare_model_data
        self.client_user = self._client_api.user
        self.client_domain = self._client_api.domain
        self.client_set_domain = self._client_api.set_domain
        self.client_packages = self._client_api.packages
        self.client_multi_packages = self._client_api.multi_packages
        self.client_organizations = self._client_api.organizations
        self.client_load_token = self._client_api.load_token
        self.client_get_api_url = self._client_api.get_api_url
        self.client_set_api_url = self._client_api.set_api_url

    # --- Helper methods
    # -------------------------------------------------------------------------
    def _set_repo_urls_from_channels(self, channels):
        """
        Convert a channel into a normalized repo name including.

        Channels are assumed in normalized url form.
        """
        repos = []
        sys_platform = self._conda_api.get_platform()

        for channel in channels:
            url = '{0}/{1}/repodata.json.bz2'.format(channel, sys_platform)
            repos.append(url)

        return repos

    def _check_repos(self, repos):
        """Check if repodata urls are valid."""
        self._checking_repos = []
        self._valid_repos = []

        for repo in repos:
            worker = self.download_is_valid_url(repo)
            worker.sig_finished.connect(self._repos_checked)
            worker.repo = repo
            self._checking_repos.append(repo)

    def _repos_checked(self, worker, output, error):
        """Callback for _check_repos."""
        if worker.repo in self._checking_repos:
            self._checking_repos.remove(worker.repo)

        if output:
            self._valid_repos.append(worker.repo)

        if len(self._checking_repos) == 0:
            self._download_repodata(self._valid_repos)

    def _repo_url_to_path(self, repo):
        """Convert a `repo` url to a file path for local storage."""
        repo = repo.replace('http://', '')
        repo = repo.replace('https://', '')
        repo = repo.replace('/', '_')

        return os.sep.join([self._data_directory, repo])

    def _download_repodata(self, checked_repos):
        """Dowload repodata."""
        self._files_downloaded = []
        self._repodata_files = []
        self.__counter = -1

        if checked_repos:
            for repo in checked_repos:
                path = self._repo_url_to_path(repo)
                self._files_downloaded.append(path)
                self._repodata_files.append(path)
                worker = self.download_async(repo, path)
                worker.url = repo
                worker.path = path
                worker.sig_finished.connect(self._repodata_downloaded)
        else:
            # Empty, maybe there is no internet connection
            # Load information from conda-meta and save that file
            path = self._get_repodata_from_meta()
            self._repodata_files = [path]
            self._repodata_downloaded()

    def _get_repodata_from_meta(self):
        """Generate repodata from local meta files."""
        path = os.sep.join([self.ROOT_PREFIX, 'conda-meta'])
        packages = os.listdir(path)
        meta_repodata = {}
        for pkg in packages:
            if pkg.endswith('.json'):
                filepath = os.sep.join([path, pkg])
                with open(filepath, 'r') as f:
                    data = json.load(f)

                if 'files' in data:
                    data.pop('files')
                if 'icondata' in data:
                    data.pop('icondata')

                name = pkg.replace('.json', '')
                meta_repodata[name] = data

        meta_repodata_path = os.sep.join([self._data_directory,
                                          'offline.json'])
        repodata = {'info': [],
                    'packages': meta_repodata}

        with open(meta_repodata_path, 'w') as f:
            json.dump(repodata, f, sort_keys=True,
                      indent=4, separators=(',', ': '))

        return meta_repodata_path

    def _repodata_downloaded(self, worker=None, output=None, error=None):
        """Callback for _download_repodata."""
        if worker:
            self._files_downloaded.remove(worker.path)

            if worker.path in self._files_downloaded:
                self._files_downloaded.remove(worker.path)

        if len(self._files_downloaded) == 0:
            self.sig_repodata_updated.emit(list(set(self._repodata_files)))

    # --- Public API
    # -------------------------------------------------------------------------
    def repodata_files(self, channels=None):
        """
        Return the repodata paths based on `channels` and the `data_directory`.

        There is no check for validity here.
        """
        if channels is None:
            channels = self.conda_get_condarc_channels()

        repodata_urls = self._set_repo_urls_from_channels(channels)

        repopaths = []

        for repourl in repodata_urls:
            fullpath = os.sep.join([self._repo_url_to_path(repourl)])
            repopaths.append(fullpath)

        return repopaths

    def set_data_directory(self, data_directory):
        """Set the directory where repodata and metadata are stored."""
        self._data_directory = data_directory

    def update_repodata(self, channels=None):
        """Update repodata from channels or use condarc channels if None."""
        norm_channels = self.conda_get_condarc_channels(channels=channels,
                                                        normalize=True)
        repodata_urls = self._set_repo_urls_from_channels(norm_channels)
        self._check_repos(repodata_urls)

    def update_metadata(self):
        """
        Update the metadata available for packages in repo.continuum.io.

        Returns a download worker.
        """
        if self._data_directory is None:
            raise Exception('Need to call `api.set_data_directory` first.')

        metadata_url = 'https://repo.continuum.io/pkgs/metadata.json'
        filepath = os.sep.join([self._data_directory, 'metadata.json'])
        worker = self.download_requests(metadata_url, filepath)
        return worker

    def check_valid_channel(self,
                            channel,
                            conda_url='https://conda.anaconda.org'):
        """Check if channel is valid."""
        if channel.startswith('https://') or channel.startswith('http://'):
            url = channel
        else:
            url = "{0}/{1}".format(conda_url, channel)

        if url[-1] == '/':
            url = url[:-1]
        plat = self.conda_platform()
        repodata_url = "{0}/{1}/{2}".format(url, plat, 'repodata.json')
        worker = self.download_is_valid_url(repodata_url)
        worker.url = url
        return worker


MANAGER_API = None


def ManagerAPI():
    """Manager API threaded worker."""
    global MANAGER_API

    if MANAGER_API is None:
        MANAGER_API = _ManagerAPI()

    return MANAGER_API


# --- Local testing
# -----------------------------------------------------------------------------
def finished(worker, output, error):  # pragma: no cover
    """Print information on test finished."""
    print(worker, output, error)


def download_finished(url, path):  # pragma: no cover
    """Print information on downlaod finished."""
    print(url, path)


def repodata_updated(repos):  # pragma: no cover
    """Print information on repodata updated."""
    print(repos)


def test():  # pragma: no cover
    """Main local test."""
    from conda_manager.utils.qthelpers import qapplication

    app = qapplication()
    api = ManagerAPI()
    api.sig_repodata_updated.connect(repodata_updated)
    data_directory = tempfile.mkdtemp()
    api.set_data_directory(data_directory)
    worker = api.update_metadata()
    worker.sig_download_finished.connect(download_finished)
    api.update_repodata()
    app.exec_()


if __name__ == '__main__':  # pragma: no cover
    test()
