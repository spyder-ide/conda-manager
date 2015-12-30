# To release a new version of **conda-manager** on PyPI:

* Install `twine`. Needed to  upload to PyPi in safe manner.

```python
pip install twine
```

* Update `_version.py` (set release version, remove 'dev')

```python
git add .
git commit -m 'comment'
python setup.py sdist
twine upload dist/*
git tag -a vX.X.X -m 'comment'
```

* Update `_version.py` (add 'dev' and increment minor)

```python
git add .
git commit -m 'comment'
git push
git push --tags
```
# To release a new version of **conda-manager** on PyPI:

`conda build conda.recipe/ -c spyder-ide`

`conda upload ***.tar.bz -u spyder-ide`
