# Changelog

- Use [setuptools-scm](https://pypi.org/project/setuptools-scm/) for
  versioning.
- [#17](https://github.com/kvas-it/pytest-console-scripts/issues/17):
  Further improved script search, run scripts that are not in
  `console_scripts`. Move the test suite to non-installable scripts and
  avoid creating virtualenvs and installing scripts during testing. The result
  is a simpler and faster test suite.
