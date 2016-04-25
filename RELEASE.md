# To release a new version of **conda-manager** on PyPI:

* git pull upstream

* Update CHANGELOG.md

* Update `_version.py` (set release version, remove 'dev0')

* git add and git commit

* python setup.py sdist upload

* python setup.py bdist_wheel upload

* git tag -a vX.X.X -m 'comment'

* Update `_version.py` (add 'dev0' and increment minor)

* git add and git commit

* git push

* git push --tags


# To release a new version of **conda-manager** for Anaconda:

* For a stable release

`conda build conda.recipe`

* For a pre-release

`PRERELEASE=True conda build conda.recipe -c spyder-ide`

* Upload to Spyder channel

`anaconda upload conda-manager-***.tar.bz2 -u spyder-ide`
