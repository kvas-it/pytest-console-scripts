pytest-console-scripts
======================

Pytest-console-scripts is a [pytest][1] plugin for running python scripts from
within tests. It's quite similar to `subprocess.run()`, but it also has an
in-process mode, where the scripts are executed by the interpreter that's
running `pytest` (using some amount of sandboxing).

In-process mode significantly reduces the run time of the test suites that
run many external scripts. This is speeds up development. In the CI environment
subprocess mode can be used to make sure the scripts also work (and behave the
same) when run by a fresh interpreter.

Requirements
------------

- Python 3.6+, or PyPy3,
- Pytest 4.0 or newer.

Installation
------------

You can install "pytest-console-scripts" via [pip][2] from [PyPI][3]:

    $ pip install pytest-console-scripts

Normally you would add it as a test dependency in `tox.ini` (see [tox
documentation][9]).

Usage
-----

This plugin will run scripts that are installed via `console_scripts` entry
point in `setup.py`, python files in current directory (or anywhere else, if
given the path), and Python scripts anywhere else in the path. It will also run
executables that are not Python scripts, but only in subprocess mode (there's
no benefit in using `pytest-console-scripts` for this, you should just use
`subprocess.run`).

Here's an example with `console_scripts` entry point. Imagine we have a python
package `foo` with the following `setup.py`:

    setup(
        name='foo',
        version='0.0.1',
        py_modules=['foo'],
        entry_points={
            'console_scripts': ['foobar=foo:bar']
        },
    )

We could use pytest-console-scripts to test the `foobar` script:

    def test_foo_bar(script_runner):
        ret = script_runner.run('foobar', '--version')
        assert ret.success
        assert ret.stdout == '3.2.1\n'
        assert ret.stderr == ''

This would use the `script_runner` fixture provided by the plugin to
run the script and capture its output.

The arguments of `script_runner.run` are the command name of the script and
any command line arguments that should be passed to it. Additionally the
following keyword arguments can be used:

- `cwd` - set the working directory of the script under test.
- `env` - a dictionary with environment variables to use instead of the current
  environment.
- `stdin` - a file-like object that will be piped to standard input of the
  script.

Configuring script execution mode
---------------------------------

In the example above the `foobar` script would run in in-process mode (which is
the default). This is fast and good for quick iteration during development.
After we're happy with the functionality, it's time to run the script in
subprocess mode to simulate real invocation more closely. There are several
ways to do this. We can configure it via pytest configuration (for example in
`tox.ini`):

     [pytest]
     script_launch_mode = subprocess

We can give a command line option to pytest (this will override the
configuration file):

    $ pytest --script-launch-mode=subprocess test_foobar.py

We can also mark individual tests to run in a specific mode:

    @pytest.mark.script_launch_mode('subprocess')
    def test_foobar(script_runner):
        ...

Between these three methods the marking of the tests has priority before the
command line option that in turn overrides the configuration setting. All three
can take three possible values: "inprocess", "subprocess", and "both" (which
will cause the test to be run twice: in in-process and in subprocess modes).

Interaction with mocking
------------------------

It is possible to mock objects and functions inside of console scripts when
they are run using `pytest-console-scripts` but only in inprocess mode. When
the script is run in subprocess mode, it is executed by a separate Python
interpreter and the test can't mock anything inside of it.

Another limitation of mocking is that with simple Python scripts that are not
installed via [`console_scripts` entry point][14] mocking of objects inside of
the main script will not work. The reason for that is that when we run
`myscript.py` with `$ python myscript.py` the script gets imported into
`__main__` namespace instead of `myscript` namespace. Our patching of
`myscript.myfunction` will have no effect on what the code in `__main__`
namespace sees when it's calling `myfunction` defined in the same file.

See [this stackoverflow answer](https://stackoverflow.com/a/66693954/1595738)
for some ideas of how to get around this.

Suppressing the printing of script run results
----------------------------------------------

When tests involving `pytest-console-scripts` fail, it tends to be quite
useful to see the output of the scripts that were executed in them. We try
to be helpful and print it out just before returning the result from
`script_runner.run()`. Normally PyTest [captures][12] all the output during a
test run and it's not shown to the user unless some tests fail. This is exactly
what we want.

However, in some cases it might be useful to disable the output capturing and
PyTest provides [ways to do it][13]. When capturing is disabled, all test run
results will be printed out and this might make it harder to inspect the other
output of the tests. To deal with this, `pytest-console-scripts` has an option
to disable the printing of script run results:

    $ pytest --hide-run-results test_foobar.py

It's also possible to disable it just for one script run:

    result = script_runner.run('foobar', print_result=False)

When printing of script run results is disabled, script output won't be
visisble even when the test fails. Unfortunately there's no automatic way to
print it only if the test fails because by the time a script run completes we
don't know whether the test will fail or not. It's possible to do it manually
from the test by using:

    result.print()

This, combined with `--hide-run-results` or `print_result=False` can be used to
only print interesting run results when capturing is off.

Package installation and testing during development
---------------------------------------------------

Since `pytest-console-scripts` relies on the scripts being located in the path,
it can only run the console scripts from packages that have been installed (if
you are interested in working on removing this limitation, take a look at [this
ticket](https://github.com/kvas-it/pytest-console-scripts/issues/34) and in
particular [this comment](https://github.com/kvas-it/pytest-console-scripts/issues/34#issuecomment-649497564)).
If you want to run the tests quickly during development, the additional
installation step would add a significant overhead and slow you down.

There's a way around this: install your package in [development mode][10] using
`python setup.py develop`. If you use [tox][9], you can take one of its
existing virtualenvs (they live in `.tox/`). Otherwise create a
[virtualenv][11] just for development, activate it and run `python setup.py
develop` to install your package in development mode. You will need to
re-install every time you add a new console script, but otherwise all the
changes to your code will be immediately picked up by the tests.

Contributing
------------

Contributions are very welcome. Tests can be run with `tox`, please ensure
the coverage at least stays the same before you submit a pull request.

License
-------

Distributed under the terms of the [MIT][8] license, "pytest-console-scripts"
is free and open source software.

Issues
------

If you encounter any problems, please [file an issue][7] along with a detailed
description.

----

Pytest-console-scripts was initially generated with [Cookiecutter][4] along
with [@hackebrot][5]'s [Cookiecutter-pytest-plugin][6] template.

[1]: https://github.com/pytest-dev/pytest
[2]: https://pypi.python.org/pypi/pip/
[3]: https://pypi.python.org/pypi
[4]: https://github.com/audreyr/cookiecutter
[5]: https://github.com/hackebrot
[6]: https://github.com/pytest-dev/cookiecutter-pytest-plugin
[7]: https://github.com/kvas-it/pytest-console-scripts/issues
[8]: http://opensource.org/licenses/MIT
[9]: https://tox.readthedocs.org/en/latest/
[10]: https://setuptools.readthedocs.io/en/latest/setuptools.html#development-mode
[11]: https://docs.python.org/3/library/venv.html
[12]: https://docs.pytest.org/en/stable/capture.html
[13]: https://docs.pytest.org/en/stable/capture.html#setting-capturing-methods-or-disabling-capturing
[14]: https://python-packaging.readthedocs.io/en/latest/command-line-scripts.html#the-console-scripts-entry-point
