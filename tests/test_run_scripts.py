"""Test running of scripts with various modes and options."""

import io
import os

import pytest


@pytest.fixture(params=['inprocess', 'subprocess'])
def launch_mode(request):
    """Launch mode: inprocess|subprocess."""
    return request.param


@pytest.fixture()
def console_script(tmpdir):
    """Python script to use in tests."""
    script = tmpdir.join('script.py')
    script.write('#!/usr/bin/env python\nprint("foo")')
    return script


@pytest.mark.script_launch_mode('both')
def test_not_installed(console_script, script_runner):
    result = script_runner.run(str(console_script))
    assert result.success
    assert result.stdout == 'foo\n'
    assert result.stderr == ''


@pytest.mark.script_launch_mode('both')
def test_elsewhere_in_the_path(console_script, script_runner):
    console_script.chmod(0o777)
    env = {'PATH': str(console_script.dirpath() + ':' + os.environ['PATH'])}
    result = script_runner.run(console_script.basename, env=env)
    assert result.success
    assert result.stdout == 'foo\n'
    assert result.stderr == ''


@pytest.mark.script_launch_mode('both')
def test_run_pytest(tmpdir, console_script, script_runner, launch_mode):
    # TODO: check if same process or not!
    console_script.write('import os;print(os.getpid())')
    test = tmpdir.join('test_{}.py'.format(launch_mode))
    compare = '==' if launch_mode == 'inprocess' else '!='
    test.write(
        """
import os
def test_script(script_runner):
    result = script_runner.run('{}')
    assert result.success
    assert result.stdout {} str(os.getpid()) + '\\n'
    assert result.stderr == ''
        """.format(console_script, compare)
    )

    # Here we're testing two things:
    #
    # - pytest is a Python script that's installed in the test environment, so
    #   we'll use `script_runner` fixture to run it -- this tests execution of
    #   installed scripts from the path.
    # - The pytest that we run will run a test that uses `script_runner`
    #   fixture to run another script. We're going to pass --script-launch-mode
    #   option to pytest and will check that the execution of the inner script
    #   is performed in accordance with its value.
    #
    # We're also testing all 4 combinations of inprocess/subprocess modes for
    # inner and outer script runners.

    result = script_runner.run(
        'pytest',
        str(test),
        '--script-launch-mode=' + launch_mode,
    )
    assert result.success


@pytest.mark.script_launch_mode('inprocess')
def test_return_None(script_runner):
    """Check that entry point function returning None is counted as success."""

    # Many console_scripts entry point functions return 0 on success but not
    # all of them do. Returning `None` is also allowed and would be translated
    # to return code 0 when run normally via wrapper. This test checks that we
    # handle this case properly in inprocess mode.
    #
    # One commonly available script that returns None from the entry point
    # function is easy_install so we use it here.

    result = script_runner.run('easy_install', '-h')
    assert result.success
    assert '--verbose' in result.stdout


@pytest.mark.script_launch_mode('both')
def test_abnormal_exit(console_script, script_runner):
    console_script.write('import sys;sys.exit("boom")')
    result = script_runner.run(str(console_script))
    assert not result.success
    assert result.stdout == ''
    assert result.stderr == 'boom\n'


@pytest.mark.script_launch_mode('both')
def test_exception(console_script, script_runner):
    console_script.write('raise TypeError("boom")')
    result = script_runner.run(str(console_script))
    assert not result.success
    assert result.stdout == ''
    assert 'TypeError: boom' in result.stderr


def test_cwd(console_script, script_runner, tmpdir):
    """Script starts in dir given by cwd arg and cwd changes are contained."""
    dir1 = tmpdir.mkdir('dir1')
    dir2 = tmpdir.mkdir('dir2')
    console_script.write(
        """
import os
print(os.getcwd())
os.chdir('{}')
print(os.getcwd())
        """.format(dir2)
    )
    mydir = os.getcwd()
    result = script_runner.run(str(console_script), cwd=str(dir1))
    assert result.success
    assert result.stdout == '{}\n{}\n'.format(dir1, dir2)
    assert os.getcwd() == mydir


@pytest.mark.script_launch_mode('both')
def test_env(console_script, script_runner):
    """Script receives environment and env changes don't escape to test."""
    console_script.write(
        """
import os
print(os.environ['FOO'])
os.environ['FOO'] = 'baz'
        """
    )
    result = script_runner.run(str(console_script), env={'FOO': 'bar'})
    assert result.success
    assert result.stdout == 'bar\n'
    assert 'FOO' not in os.environ


@pytest.mark.script_launch_mode('both')
def test_stdin(console_script, script_runner):
    console_script.write(
        """
import sys
for line in sys.stdin:
    sys.stdout.write('simon says ' + line)
    sys.stderr.write('error says ' + line)
        """
    )
    stdin = io.StringIO('foo\nbar')
    result = script_runner.run(str(console_script), stdin=stdin)
    assert result.success
    assert result.stdout == 'simon says foo\nsimon says bar'
    assert result.stderr == 'error says foo\nerror says bar'


def test_logging(console_script, script_runner):
    """Test that the script can perform logging initialization."""
    console_script.write(
        """
import logging, sys
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logging.debug('hidden')
logging.info('shown')
        """
    )
    result = script_runner.run(str(console_script))
    assert result.success
    assert result.stderr == 'INFO:root:shown\n'


@pytest.mark.parametrize('fail', [True, False])
def test_print_stdio_on_error(console_script, script_runner, tmpdir, fail,
                              launch_mode):
    """Output of the script is printed when the test fails."""
    console_script.write('print("12345")\nraise Exception("54321")')
    test = tmpdir.join('test_{}_{}.py'.format(fail, launch_mode))
    test.write(
        """
def test_fail(script_runner):
    ret = script_runner.run('{}', 'arg')
    assert ret.success is {}
        """.format(console_script, fail)
    )
    result = script_runner.run(
        'pytest',
        str(test),
        '--script-launch-mode=' + launch_mode,
    )
    assert result.success != fail
    if fail:
        assert ('# Running console script: {} arg\n'.format(console_script)
                in result.stdout)
        assert '# Script return code: 1\n' in result.stdout
        assert '# Script stdout:\n12345\n' in result.stdout
        assert '# Script stderr:\nTraceback' in result.stdout
        assert 'Exception: 54321' in result.stdout
    else:
        assert '# Running console script' not in result.stdout
        assert '12345' not in result.stdout
        assert '54321' not in result.stdout
