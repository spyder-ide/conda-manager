|license| |pypi version| |pypi download| |pypi versions| |Build status|

.. |license| image:: https://img.shields.io/pypi/l/conda-manager.svg
   :target: LICENSE.txt
   :alt: License
.. |pypi version| image:: https://img.shields.io/pypi/v/conda-manager.svg
   :target: https://pypi.python.org/pypi/conda-manager/
   :alt: Latest PyPI version
.. |pypi download| image:: https://img.shields.io/pypi/dm/conda-manager.svg
   :target: https://pypi.python.org/pypi/conda-manager
   :alt: Number of PyPI downloads
.. |pypi versions| image:: https://img.shields.io/pypi/pyversions/conda-manager.svg
   :target: https://pypi.python.org/pypi/conda-manager
   :alt: Supported Python version
.. |Build status| image:: https://travis-ci.org/spyder-ide/conda-manager.svg?branch=master
   :target: https://travis-ci.org/spyder-ide/conda-manager
   :alt: Travis-CI build status


Description
-----------

**conda-manager** is a stand alone Qt application (PySide, PyQt4, PyQt5)
providing a friendly graphical user interface for the management (update, 
downgrade, installation and removal) of `conda`_ packages and environments.

- `Issue tracker`_
- `Changelog`_

Standalone app
--------------
.. image:: https://raw.githubusercontent.com/spyder-ide/conda-manager/master/img_src/screenshot.png
    :align: center
    :alt: Conda Package Manager


Spyder plugin
-------------
.. image:: https://raw.githubusercontent.com/spyder-ide/conda-manager/master/img_src/screenshot-spyder.png
    :align: center
    :alt: Conda Package Manager

This project also installs as a plugin for `Spyder`_ to manage conda packages
from within the application.


License
-------

This project is licensed under the MIT license.


Installation
------------
::

  conda install conda-manager

or

::

  pip install conda-manager


.. _conda: https://github.com/conda/conda
.. _spyder: https://github.com/spyder-ide/spyder
.. _Changelog: https://github.com/spyder-ide/conda-manager/blob/master/CHANGELOG.md
.. _Issue tracker: https://github.com/spyder-ide/conda-manager/issues
