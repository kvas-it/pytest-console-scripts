import os
import subprocess
import sys

import mock
import py
import pytest
import virtualenv


# Template for creating setup.py for installing console scripts.
SETUP_TEMPLATE = """
import setuptools

setuptools.setup(
    name='{script_name}',
    version='1.0',
    py_modules=['{script_name}'],
    zip_safe=False,
    entry_points={{
        'console_scripts': ['{cmd}={script_name}:main']
    }}
)
"""


class VEnvWrapper:
    """Wrapper for virtualenv that can execute code inside of it."""

    def __init__(self, path):
        self.path = path
        dpp = self._distpackages_path()
        if dpp is not None:
            self.path.mkdir(dpp)

    def _distpackages_path(self):
        """Return (relative) path used for installing distribution packages.

        On Debian-based systems packages are installed into .../dist-packages
        instead of .../site-packages. This function returns the relative path
        of this directory inside of a virtualenv so that we can create it and
        avoid setup.py failure.

        Will return `None` on systems that don't do this or when running inside
        of a virtualenv.
        """
        for path in sys.path:
            if path.endswith('dist-packages'):
                parts = path.split(os.path.sep)
                if 'lib' in parts:
                    parts = parts[parts.index('lib'):]
                    return os.path.join(*parts)

    def _update_env(self, env):
        bin_dir = self.path.join('bin').strpath
        env['PATH'] = bin_dir + ':' + env.get('PATH', '')
        env['VIRTUAL_ENV'] = self.path.strpath
        # Make installed packages of the Python installation that runs this
        # test accessible. This allows us to run tests in the virtualenv
        # without installing all the dependencies there.
        env['PYTHONPATH'] = ':'.join(sys.path)

    def run(self, cmd, *args, **kw):
        """Run a command in the virtualenv, return terminated process."""
        self._update_env(kw.setdefault('env', dict(os.environ)))
        kw.setdefault('stdout', subprocess.PIPE)
        kw.setdefault('stderr', subprocess.PIPE)
        proc = subprocess.Popen(cmd, *args, **kw)
        proc.wait()
        return proc

    def install_console_script(self, cmd, script_path):
        """Run setup.py to install console script into this virtualenv."""
        script_dir = script_path.dirpath()
        script_name = script_path.purebasename
        setup_py = script_dir.join('setup.py')
        setup_py.write(SETUP_TEMPLATE.format(cmd=cmd, script_name=script_name))
        self.run(['python', 'setup.py', 'develop'], cwd=str(script_dir))


@pytest.fixture(scope='session')
def pcs_venv(tmpdir_factory):
    """Virtualenv for testing console scripts."""
    venv = tmpdir_factory.mktemp('venv')
    virtualenv.create_environment(venv.strpath)
    yield VEnvWrapper(venv)


@pytest.fixture(scope='session')
def console_script(pcs_venv, tmpdir_factory):
    """Console script exposed as a wrapper in python `bin` directory.

    Returned value is a `py.path.local` object that corresponds to a python
    file whose `main` function is exposed via console script wrapper. The
    name of the command is available via it `command_name` attribute.

    The fixture is made session scoped for speed. The idea is that every test
    will overwrite the content of the script exposed by this fixture to get
    the behavior that it needs.
    """
    script_dir = tmpdir_factory.mktemp('script')
    script = script_dir.join('console_script.py')
    pyc = script_dir.join('console_script.pyc')
    cache_dir = script_dir.join('__pycache__')
    script.write('def main(): pass')
    pcs_venv.install_console_script('console-script', script)

    def replace(new_source):
        """Replace script source."""
        script.write(new_source)
        # Remove stale bytecode that causes heisenbugs on py27 and pypy.
        if pyc.check():
            pyc.remove()
        if cache_dir.check():
            cache_dir.remove(rec=1)

    script.replace = replace
    return script


@pytest.fixture(params=['inprocess', 'subprocess'])
def launch_mode(request):
    """Launch mode: inprocess|subprocess."""
    return request.param


@pytest.fixture()
def run_script_in_venv(pcs_venv, console_script, tmpdir, launch_mode):
    """A fixture that tests provided script with provided test."""

    def run(script_src, test_src, **kw):
        """Test provided script with a provided test."""
        console_script.replace(script_src)
        test = tmpdir.join('test.py')
        test.write(test_src)
        # Execute pytest with the python of the virtualenv we created,
        # otherwise it would be executed with the python that runs this test,
        # which is wrong.
        test_cmd = [
            'python',
            '-m', 'pytest',
            '--script-launch-mode=' + launch_mode,
            test.strpath,
        ]
        return pcs_venv.run(test_cmd, **kw)

    return run


@pytest.fixture()
def test_script_in_venv(run_script_in_venv):
    """Tests provided script with provided test and check that it passed."""

    def test(script_src, test_src, **kw):
        proc = run_script_in_venv(script_src, test_src, **kw)
        print('--- test run stdout ---')
        print(proc.stdout.read().decode('utf-8'))
        print('--- test run stderr ---')
        print(proc.stderr.read().decode('utf-8'))
        assert proc.returncode == 0

    return test


@pytest.mark.parametrize('script,test', [
    (
        """
from __future__ import print_function

def main():
    print(u'hello world')
    print('hello world')
        """,
        r"""
def test_hello_world(script_runner):
    ret = script_runner.run('console-script')
    print(ret.stderr)
    assert ret.success
    assert ret.stdout == 'hello world\nhello world\n'
        """,
    ),
    # Script that exits abnormally.
    (
        """
import sys

def main():
    sys.exit('boom')
        """,
        r"""
def test_exit_boom(script_runner):
    ret = script_runner.run('console-script')
    assert not ret.success
    assert ret.stdout == ''
    assert ret.stderr == 'boom\n'
        """,
    ),
    # Script that has an uncaught exception.
    (
        """
import sys

def main():
    raise TypeError('boom')
        """,
        r"""
def test_throw_exception(script_runner):
    ret = script_runner.run('console-script')
    assert not ret.success
    assert ret.returncode == 1
    assert ret.stdout == ''
    assert 'TypeError: boom' in ret.stderr
        """,
    ),
    # Script that changes to another directory. The test process should remain
    # in the directory where it was (this is particularly relevant if we run
    # the script inprocess).
    (
        """
from __future__ import print_function

import os
import sys

def main():
    os.chdir(sys.argv[1])
    print(os.getcwd())
        """,
        r"""
import os

def test_preserve_cwd(script_runner, tmpdir):
    dir1 = tmpdir.mkdir('dir1')
    dir2 = tmpdir.mkdir('dir2')
    os.chdir(str(dir1))
    ret = script_runner.run('console-script', str(dir2))
    assert ret.stdout == str(dir2) + '\n'
    assert os.getcwd() == str(dir1)
        """,
    ),
    # Send input to tested script's stdin.
    (
        """
import sys

def main():
    for line in sys.stdin:
        sys.stdout.write('simon says ' + line)
        """,
        r"""
import io

def test_stdin(script_runner):
    ret = script_runner.run('console-script', stdin=io.StringIO(u'foo\nbar'))
    assert ret.success
    assert ret.stdout == 'simon says foo\nsimon says bar'
        """,
    ),
])
def test_run_script(test_script_in_venv, script, test):
    test_script_in_venv(script, test)


def test_run_script_with_cwd(test_script_in_venv, tmpdir):
    test_script_in_venv(
        """
from __future__ import print_function

import os

def main():
    print(os.getcwd())
        """,
        r"""
def test_cwd(script_runner):
    ret = script_runner.run('console-script', cwd='{cwd}')
    assert ret.success
    assert ret.stdout == '{cwd}\n'
        """.format(cwd=tmpdir),
    )


def test_set_env_inprocess(test_script_in_venv):
    test_script_in_venv(
        """
from __future__ import print_function

import os

def main():
    print(os.environ['FOO'])
        """,
        r"""
import pytest

@pytest.mark.script_launch_mode('inprocess')
def test_env(script_runner):
    ret = script_runner.run('console-script', env={'FOO': 'bar'})
    assert ret.success
    assert 'bar\n' == ret.stdout
        """
    )


@pytest.mark.parametrize('fail', [True, False])
def test_print_stdio_on_error(run_script_in_venv, fail):
    """Check that the content of stdout and stderr is printed on error."""
    proc = run_script_in_venv(
        """
from __future__ import print_function

def main():
    print('12345')
    raise Exception('54321')
        """,
        """
def test_fail(script_runner):
    ret = script_runner.run('console-script', 'foo')
    assert ret.success is {}
        """.format(fail),
    )
    stdout = proc.stdout.read()
    if type(stdout) != type(''):  # In Python 3 we convert stdout to unicode.
        stdout = stdout.decode('utf-8')
    if fail:
        assert proc.returncode != 0
        assert '# Running console script: console-script foo\n' in stdout
        assert '# Script return code: 1\n' in stdout
        assert '# Script stdout:\n12345\n' in stdout
        assert '# Script stderr:\nTraceback' in stdout
        assert 'Exception: 54321' in stdout
    else:
        assert proc.returncode == 0
        assert 'console-script foo' not in stdout
        assert '12345' not in stdout
        assert '54321' not in stdout


def test_basic_logging(test_script_in_venv):
    test_script_in_venv(
        """
import logging
import sys

def main():
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    logging.debug('hidden')
    logging.info('shown')
        """,
        r"""
import pytest

def test_env(script_runner):
    ret = script_runner.run('console-script')
    assert ret.success
    assert ret.stderr == 'INFO:root:shown\n'
        """
    )
