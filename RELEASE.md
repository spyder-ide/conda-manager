# To release a new version of **conda-manager** on PyPI:

* Install `twine`. Needed to  upload to PyPi in safe manner.

```bash
pip install twine
```

* Update `_version.py` (set release version, remove 'dev')

```bash
git add .
git commit -m 'comment'
python setup.py sdist
twine upload dist/*
git tag -a vX.X.X -m 'comment'
```

* Update `_version.py` (add 'dev' and increment minor)

```bash
git add .
git commit -m 'comment'
git push
git push --tags
```

# To release a new version of **conda-manager** for Anaconda:

* For a stable release

`conda build conda.recipe`

* For a pre-release

`PRERELEASE=True conda build conda.recipe -c spyder-ide`

* Upload to Spyder channel

`anaconda upload conda-manager-***.tar.bz2 -u spyder-ide`
