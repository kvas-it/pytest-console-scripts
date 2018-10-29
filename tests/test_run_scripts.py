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

    def _update_env(self, env):
        bin_dir = self.path.join('bin').strpath
        env['PATH'] = bin_dir + ':' + env.get('PATH', '')
        env['VIRTUAL_ENV'] = self.path.strpath
        env['PYTHONPATH'] = ':'.join(sys.path)

    def run(self, cmd, *args, **kw):
        """Run a command in the virtualenv."""
        self._update_env(kw.setdefault('env', os.environ))
        print(kw['env']['PATH'], kw['env']['PYTHONPATH'])
        subprocess.check_call(cmd, *args, **kw)

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
    script = tmpdir_factory.mktemp('script').join('console_script.py')
    script.write('def main(): pass')
    pcs_venv.install_console_script('console-script', script)

    def replace(new_source):
        """Replace script source."""
        script.write(new_source)
        pyc = script.strpath + 'c'
        if os.path.exists(pyc):
            # Remove stale bytecode that causes heisenbugs on py27.
            os.remove(pyc)

    script.replace = replace
    return script


@pytest.fixture(params=['inprocess', 'subprocess'])
def launch_mode(request):
    """Launch mode: inprocess|subprocess."""
    return request.param


@pytest.fixture
def test_script_in_venv(pcs_venv, console_script, tmpdir, launch_mode):
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
        pcs_venv.run(test_cmd, **kw)

    return run


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
