pytest-console-scripts
===================================

.. image:: https://travis-ci.org/kvas-it/pytest-console-scripts.svg?branch=master
    :target: https://travis-ci.org/kvas-it/pytest-console-scripts
    :alt: See Build Status on Travis CI

Pytest-console-scripts is a `Pytest`_ plugin for testing python scripts
installed via ``console_scripts`` entry point of ``setup.py``. It can run the
scripts under test in a separate process or using the interpreter that's
running the test suite.  The former mode ensures that the script will run in an
environment that is identical to normal execution whereas the latter one allows
much quicker test runs during development while simulating the real runs as
much as possible.


Requirements
------------

* Python 2.7 or 3.4+, or PyPy,
* Pytest 4.0 or newer.


Installation
------------

You can install "pytest-console-scripts" via `pip`_ from `PyPI`_::

    $ pip install pytest-console-scripts


Usage
-----

Imagine we have a python package ``foo`` with the following ``setup.py``:

.. code-block:: python

    setup(
        name='foo',
        version='0.0.1',
        py_modules=['foo'],
        entry_points={
            'console_scripts': ['foobar=foo:bar']
        },
    )

We could use pytest-console-scripts to test the ``foobar`` script:

.. code-block:: python

    def test_foo_bar(script_runner):
        ret = script_runner.run('foobar', '--version')
        assert ret.success
        # just for example, let's assume that foobar --version 
        # should output 3.2.1
        assert ret.stdout == '3.2.1\n'
        assert ret.stderr == ''

This would use the ``script_runner`` fixture provided by the plugin to
run the script and capture it's output.

The arguments of ``script_runner.run`` are the command name of the script and
any command line arguments that should be passed to it. Additionally the
following keyword arguments can be used:

- ``cwd`` - set the working directory of the script under test.
- ``stdin`` - a file-like object that will be piped to standard input of the
  script.

Configuring script execution mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the example above the ``foobar`` script would run in in-process mode. This
is fast and good for quick iteration during development. After we're happy with
the functionality, it's time to run the script in subprocess mode to simulate
real invocation more closely. There are several ways to do this. We can
configure it via pytest configuration (for example in ``tox.ini``):

.. code-block:: ini

     [pytest]
     script_launch_mode = subprocess

We can give a command line option to pytest (this will override the
configuration file)::

    $ py.test --script-launch-mode=subprocess test_foobar.py

We can also mark individual tests to run in a specific mode:

.. code-block:: python

    @pytest.mark.script_launch_mode('subprocess')
    def test_foobar(script_runner):
        ...

Between these three methods the marking of the tests has priority before the
command line option that in turn overrides the configuration setting. All three
can take three possible values: "inprocess" (which is the default),
"subprocess", and "both" (which will cause the test to be run twice: in
inprocess and in subprocess modes).


Contributing
------------
Contributions are very welcome. Tests can be run with `tox`_, please ensure
the coverage at least stays the same before you submit a pull request.


License
-------

Distributed under the terms of the `MIT`_ license, "pytest-console-scripts"
is free and open source software.


Issues
------

If you encounter any problems, please `file an issue`_ along with a detailed
description.


----

Pytest-console-scripts was initially generated with `Cookiecutter`_ along with
`@hackebrot`_'s `Cookiecutter-pytest-plugin`_ template.

.. _`Cookiecutter`: https://github.com/audreyr/cookiecutter
.. _`@hackebrot`: https://github.com/hackebrot
.. _`MIT`: http://opensource.org/licenses/MIT
.. _`cookiecutter-pytest-plugin`: https://github.com/pytest-dev/cookiecutter-pytest-plugin
.. _`file an issue`: https://github.com/kvas-it/pytest-console-scripts/issues
.. _`pytest`: https://github.com/pytest-dev/pytest
.. _`tox`: https://tox.readthedocs.org/en/latest/
.. _`pip`: https://pypi.python.org/pypi/pip/
.. _`PyPI`: https://pypi.python.org/pypi
