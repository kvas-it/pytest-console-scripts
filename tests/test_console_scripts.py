from __future__ import print_function, unicode_literals

import subprocess

import mock
import pytest


@pytest.fixture(params=[None, 'inprocess', 'subprocess', 'both'])
def launch_mode_conf(request):
    """Configured launch mode (None|'inprocess'|'subprocess'|'both')."""
    return request.param


@pytest.fixture
def launch_modes(launch_mode_conf):
    """Set of launch modes in which the tests will actually be run.

    The value of this fixture depends on the value of `launch_mode_conf`:
    - 'inprocess'  -> {'inprocess'}
    - 'subprocess' -> {'subprocess'}
    - 'both'       -> {'inprocess', 'subprocess'}
    - None         -> {'inprocess'}
    """
    if launch_mode_conf == 'both':
        return {'inprocess', 'subprocess'}
    if launch_mode_conf is not None:
        return {launch_mode_conf}
    return {'inprocess'}


@pytest.fixture
def run_test(testdir):
    def runner(script, passed=1, skipped=0, failed=0, launch_mode_conf=None):
        testdir.makepyfile(script)
        args = []
        if launch_mode_conf is not None:
            args.append('--script-launch-mode=' + launch_mode_conf)
        result = testdir.runpytest(*args)
        print('\n'.join(['pytest stdout:'] + result.outlines +
                        ['pytest stderr:'] + result.errlines))
        result.assert_outcomes(passed=passed, skipped=skipped, failed=failed)
        return result
    return runner


CHECK_LAUNCH_MODE = """
def test_both(script_runner, accumulator=set()):
    assert script_runner.launch_mode in {}
    assert script_runner.launch_mode not in accumulator
    accumulator.add(script_runner.launch_mode)
"""


def test_command_line_option(run_test, launch_mode_conf, launch_modes):
    run_test(
        CHECK_LAUNCH_MODE.format(launch_modes),
        passed=len(launch_modes),
        launch_mode_conf=launch_mode_conf
    )


def test_config_option(run_test, testdir, launch_mode_conf, launch_modes):
    if launch_mode_conf is not None:
        testdir.makeini("""
            [pytest]
            script_launch_mode = {}
        """.format(launch_mode_conf))

    run_test(
        CHECK_LAUNCH_MODE.format(launch_modes),
        passed=len(launch_modes)
    )


def test_override_launch_mode_with_mark(run_test, launch_mode_conf):
    run_test(
        """
import pytest

@pytest.mark.script_launch_mode('inprocess')
def test_inprocess(script_runner):
    assert script_runner.launch_mode == 'inprocess'

@pytest.mark.script_launch_mode('subprocess')
def test_subprocess(script_runner):
    assert script_runner.launch_mode == 'subprocess'

@pytest.mark.script_launch_mode('both')
def test_both(script_runner, accumulator=set()):
    assert script_runner.launch_mode not in accumulator
    accumulator.add(script_runner.launch_mode)
        """,
        passed=4,
        launch_mode_conf=launch_mode_conf
    )


def test_help_message(testdir):
    result = testdir.runpytest(
        '--help',
    )
    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines([
        'console-scripts:',
        '*--script-launch-mode=*',
    ])


def run_setup_py(cmd, script_path, uninstall=False):
    """Run setup.py to install or uninstall the script command line wrapper."""
    script_dir = script_path.join('..')
    script_name = script_path.purebasename
    setup_py = script_dir.join('setup.py')
    setup_py.write(
        """
import setuptools

setuptools.setup(
    name='{script_name}',
    version='0.1',
    py_modules=['{script_name}'],
    zip_safe=False,
    entry_points={{
        'console_scripts': ['{cmd}={script_name}:main']
    }}
)
        """.format(cmd=cmd, script_name=script_name))
    args = ['setup.py', 'develop']
    if uninstall:
        args.append('--uninstall')
    try:
        with script_dir.as_cwd(), mock.patch('sys.argv', args):
            exec(setup_py.read())
    except TypeError:
        # In-process call fails on some Python 2 installations
        # but it's faster, especially on PyPy.
        subprocess.check_call(['python'] + args, cwd=str(script_dir))


@pytest.yield_fixture
def console_script(request, testdir):
    """Console script exposed as a wrapper in python `bin` directory.

    Returned value is a `py.path.local` object that corresponds to a python
    file whose `main` function is exposed via console script wrapper. The
    name of the command is available via it `command_name` attribute.
    """
    script = testdir.makepyfile(console_script_module='def main(): pass')
    cmd = 'console-script-module-cmd'
    run_setup_py(cmd, script)
    script.command_name = cmd
    yield script
    run_setup_py(cmd, script, uninstall=True)


@pytest.fixture(params=['inprocess', 'subprocess'])
def launch_mode(request):
    """Launch mode: inprocess|subprocess."""
    return request.param


def test_run_script(console_script, run_test, launch_mode):
    console_script.write(
        """
from __future__ import print_function

def main():
    print(u'hello world')
    print('hello world')
        """
    )
    run_test(
        r"""
def test_hello_world(script_runner):
    ret = script_runner.run('{}')
    print(ret.stderr)
    assert ret.success
    assert ret.stdout == 'hello world\nhello world\n'
        """.format(console_script.command_name),
        launch_mode_conf=launch_mode,
        passed=1
    )


def test_run_failing_script(console_script, run_test, launch_mode):
    console_script.write(
        """
import sys

def main():
    sys.exit('boom')
        """
    )
    run_test(
        r"""
def test_exit_boom(script_runner):
    ret = script_runner.run('{}')
    assert not ret.success
    assert ret.stdout == ''
    assert ret.stderr == 'boom\n'
        """.format(console_script.command_name),
        launch_mode_conf=launch_mode,
        passed=1
    )


def test_run_script_with_exception(console_script, run_test, launch_mode):
    console_script.write(
        """
import sys

def main():
    raise TypeError('boom')
        """
    )
    run_test(
        r"""
def test_throw_exception(script_runner):
    ret = script_runner.run('{}')
    assert not ret.success
    assert ret.returncode == 1
    assert ret.stdout == ''
    assert 'TypeError: boom' in ret.stderr
        """.format(console_script.command_name),
        launch_mode_conf=launch_mode,
        passed=1
    )


def test_run_script_with_cwd(console_script, run_test, launch_mode, tmpdir):
    console_script.write(
        """
from __future__ import print_function

import os

def main():
    print(os.getcwd())
        """
    )
    run_test(
        r"""
def test_cwd(script_runner):
    ret = script_runner.run('{script_name}', cwd='{cwd}')
    assert ret.success
    assert ret.stdout == '{cwd}\n'
        """.format(script_name=console_script.command_name, cwd=tmpdir),
        launch_mode_conf=launch_mode
    )


def test_preserve_cwd(console_script, run_test, launch_mode):
    console_script.write(
        """
from __future__ import print_function

import os
import sys

def main():
    os.chdir(sys.argv[1])
    print(os.getcwd())
        """
    )
    run_test(
        r"""
import os

def test_preserve_cwd(script_runner, tmpdir):
    dir1 = tmpdir.mkdir('dir1')
    dir2 = tmpdir.mkdir('dir2')
    os.chdir(str(dir1))
    ret = script_runner.run('{script_name}', str(dir2))
    assert ret.stdout == str(dir2) + '\n'
    assert os.getcwd() == str(dir1)
        """.format(script_name=console_script.command_name)
    )


def test_run_script_with_stdin(console_script, run_test, launch_mode):
    console_script.write(
        """
import sys

def main():
    for line in sys.stdin:
        sys.stdout.write('simon says ' + line)
        """
    )
    run_test(
        r"""
import io

def test_stdin(script_runner):
    ret = script_runner.run('{script_name}', stdin=io.StringIO(u'foo\nbar'))
    assert ret.success
    assert ret.stdout == 'simon says foo\nsimon says bar'
        """.format(script_name=console_script.command_name),
        launch_mode_conf=launch_mode
    )
