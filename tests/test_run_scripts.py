"""Test running of scripts with various modes and options."""
from __future__ import annotations

import contextlib
import importlib
import io
import os
import sys
from pathlib import Path
from subprocess import CalledProcessError
from types import ModuleType
from typing import Any, ContextManager
from unittest import mock

import pytest

from pytest_console_scripts import ScriptRunner


@pytest.fixture(params=['inprocess', 'subprocess'])
def launch_mode(request: pytest.FixtureRequest) -> str:
    """Launch mode: inprocess|subprocess."""
    return str(request.param)


@pytest.fixture()
def console_script(tmp_path: Path) -> Path:
    """Python script to use in tests."""
    script = tmp_path / 'script.py'
    script.write_text('#!/usr/bin/env python\nprint("foo")')
    return script


@pytest.mark.script_launch_mode('both')
def test_not_installed(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    result = script_runner.run(str(console_script))
    assert result.success
    assert result.stdout == 'foo\n'
    assert result.stderr == ''


@pytest.mark.xfail(
    sys.platform == "win32",
    reason="Windows does not treat Python scripts as executables."
)
@pytest.mark.script_launch_mode('both')
def test_elsewhere_in_the_path(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    console_script.chmod(0o777)
    env = os.environ.copy()
    env["PATH"] = f"{console_script.parent}{os.pathsep}{env['PATH']}"
    result = script_runner.run(console_script.name, env=env)
    assert result.success
    assert result.stdout == 'foo\n'
    assert result.stderr == ''


@pytest.mark.script_launch_mode('both')
def test_run_pytest(
    tmp_path: Path,
    console_script: Path,
    script_runner: ScriptRunner,
    launch_mode: str
) -> None:
    console_script.write_text('import os;print(os.getpid())')
    test = tmp_path / f'test_{launch_mode}.py'
    compare = '==' if launch_mode == 'inprocess' else '!='
    test.write_text(
        f"""
import os
def test_script(script_runner):
    result = script_runner.run(R'''{console_script}''')
    assert result.success
    assert result.stdout {compare} str(os.getpid()) + '\\n'
    assert result.stderr == ''
        """
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
        ['pytest', test, f'--script-launch-mode={launch_mode}']
    )
    assert result.success


@pytest.mark.script_launch_mode('inprocess')
def test_return_None(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    """Check that entry point function returning None is counted as success."""
    # Many console_scripts entry point functions return 0 on success but not
    # all of them do. Returning `None` is also allowed and would be translated
    # to return code 0 when run normally via wrapper. This test checks that we
    # handle this case properly in inprocess mode.
    console_script.write_text(
        """
import sys
print("Foo")
sys.exit(None)
"""
    )
    result = script_runner.run(str(console_script))
    assert result.success
    assert 'Foo' in result.stdout


@pytest.mark.script_launch_mode('inprocess')
def test_return_code_uncommon(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    """Check uncommon return codes."""
    console_script.write_text(
        """
import sys
sys.exit(2)
"""
    )
    assert script_runner.run(str(console_script)).returncode == 2


@pytest.mark.script_launch_mode('both')
def test_abnormal_exit(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    console_script.write_text('import sys;sys.exit("boom")')
    result = script_runner.run(str(console_script))
    assert not result.success
    assert result.stdout == ''
    assert result.stderr == 'boom\n'


@pytest.mark.script_launch_mode('both')
def test_exception(console_script: Path, script_runner: ScriptRunner) -> None:
    console_script.write_text('raise TypeError("boom")')
    result = script_runner.run(str(console_script))
    assert not result.success
    assert result.stdout == ''
    assert 'TypeError: boom' in result.stderr


def test_cwd(
    console_script: Path,
    script_runner: ScriptRunner,
    tmp_path: Path,
) -> None:
    """Script starts in dir given by cwd arg and cwd changes are contained."""
    dir1 = tmp_path / 'dir1'
    dir1.mkdir()
    dir2 = tmp_path / 'dir2'
    dir2.mkdir()
    console_script.write_text(
        f"""
import os
print(os.getcwd())
os.chdir(R'''{dir2}''')
print(os.getcwd())
        """
    )
    mydir = os.getcwd()
    result = script_runner.run(str(console_script), cwd=str(dir1))
    assert result.success
    assert result.stdout == f'{dir1}\n{dir2}\n'
    assert os.getcwd() == mydir


@pytest.mark.script_launch_mode('both')
def test_env(console_script: Path, script_runner: ScriptRunner) -> None:
    """Script receives environment and env changes don't escape to test."""
    console_script.write_text(
        """
import os
print(os.environ['FOO'])
os.environ['FOO'] = 'baz'
        """
    )
    env = os.environ.copy()
    env['FOO'] = 'bar'
    result = script_runner.run(str(console_script), env=env)
    assert result.success
    assert result.stdout == 'bar\n'
    assert 'FOO' not in os.environ


@pytest.mark.script_launch_mode('both')
def test_stdin(console_script: Path, script_runner: ScriptRunner) -> None:
    console_script.write_text(
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


def test_logging(console_script: Path, script_runner: ScriptRunner) -> None:
    """Test that the script can perform logging initialization."""
    console_script.write_text(
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
@pytest.mark.parametrize('check', [True, False])
def test_print_stdio_on_error(
    console_script: Path,
    script_runner: ScriptRunner,
    tmp_path: Path,
    fail: bool,
    check: bool,
    launch_mode: str,
) -> None:
    """Output of the script is printed when the test fails."""
    console_script.write_text('print("12345")\nraise Exception("54321")')
    test = tmp_path / f'test_{fail}_{check}_{launch_mode}.py'
    command = [str(console_script), 'arg']
    test.write_text(
        f"""
import subprocess

def test_fail(script_runner):
    try:
        ret = script_runner.run({command}, check={check})
    except subprocess.CalledProcessError as exc:
        assert (exc.returncode == 0) is {fail}
    else:
        assert ret.success is {fail}
        """
    )
    result = script_runner.run(
        ['pytest', test, f'--script-launch-mode={launch_mode}']
    )
    assert result.success != fail
    if fail:
        assert (f'# Running console script: {command}\n'
                in result.stdout)
        assert '# Script return code: 1\n' in result.stdout
        assert '# Script stdout:\n12345\n' in result.stdout
        assert '# Script stderr:\nTraceback' in result.stdout
        assert 'Exception: 54321' in result.stdout
    else:
        assert '# Running console script' not in result.stdout
        assert '12345' not in result.stdout
        assert '54321' not in result.stdout


@pytest.mark.script_launch_mode('inprocess')
def test_mocking(
    console_script: Path,
    script_runner: ScriptRunner,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test mocking in of console scripts (in-process mode only).

    Note: we can't mock objects in the script itself because it will not be
    imported via normal import system but we can mock anything in the modules
    that the script imports.

    """
    console_script.write_text(
        """
import os
print(os.path.basename('foo'))
        """
    )
    monkeypatch.setattr(os.path, 'basename', lambda foo: 'bar')
    result = script_runner.run(str(console_script))
    assert result.success
    assert result.stdout == 'bar\n'


def test_hide_run_result_arg(
    tmp_path: Path, console_script: Path, script_runner: ScriptRunner
) -> None:
    """Disable printing of the RunResult to stdout with print_result=False."""
    console_script.write_text('print("the answer is 42")')
    test = tmp_path / 'test_hrra.py'
    test.write_text(
        f"""
import pytest

@pytest.mark.script_launch_mode('both')
def test_script(script_runner):
    script_runner.run(R'''{console_script}''', print_result=False)
        """
    )
    result = script_runner.run(['pytest', '-s', test])
    assert result.success
    assert 'the answer is 42' not in result.stdout
    assert 'Running console script' not in result.stdout


def test_hide_run_result_opt(
    tmp_path: Path, console_script: Path, script_runner: ScriptRunner
) -> None:
    """Disable printing of the RunResult to stdout with print_result=False."""
    console_script.write_text('print("the answer is 42")')
    test = tmp_path / 'test_hrro.py'
    test.write_text(
        f"""
import pytest

@pytest.mark.script_launch_mode('both')
def test_script(script_runner):
    script_runner.run(R'''{console_script}''')
        """
    )
    result = script_runner.run(['pytest', '-s', '--hide-run-results', test])
    assert result.success
    assert 'the answer is 42' not in result.stdout
    assert 'Running console script' not in result.stdout


class MockEntryPoint:
    module: ModuleType

    def __init__(self, exec_path: str | Path):
        self.exec_path = exec_path

    def load(self) -> Any:
        base, module = os.path.split(self.exec_path)
        module_name, _ = os.path.splitext(module)
        sys.path.append(base)
        self.module = importlib.import_module(module_name)
        sys.path.pop(-1)
        return self.module.run


@pytest.mark.script_launch_mode('inprocess')
def test_global_logging(
    tmp_path: Path, console_script: Path, script_runner: ScriptRunner
) -> None:
    """Load global values when executing from importlib.metadata"""
    test = tmp_path / 'test_entry_point.py'
    test.write_text(
        """
import logging

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def run() -> None:
    LOGGER.debug('DEBUG')
    LOGGER.info('INFO')
    LOGGER.warning('WARNING')
        """
    )

    if sys.version_info < (3, 10):
        patched_func = 'importlib_metadata.entry_points'
    else:
        patched_func = 'importlib.metadata.entry_points'

    with mock.patch(
        patched_func,
        mock.MagicMock(return_value=[MockEntryPoint(str(test))]),
    ):
        result = script_runner.run(str(console_script))
        assert result.success
        assert 'INFO:test_entry_point:INFO\n' in result.stderr
        assert 'DEBUG\n' not in result.stderr


@pytest.mark.script_launch_mode('both')
def test_shell(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    console_script.chmod(0o777)
    result = script_runner.run(
        f"{console_script} --test", shell=True, check=True
    )
    assert result.stdout == 'foo\n'
    assert result.stderr == ''
    result = script_runner.run(
        [str(console_script), "--test"], shell=True, check=True
    )
    assert result.stdout == 'foo\n'
    assert result.stderr == ''


@pytest.mark.script_launch_mode('both')
def test_deprecated_args(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    console_script.write_text(
        """
import sys
print(sys.argv[1:])
        """
    )
    with pytest.warns(match=r".*multiple arguments."):
        result = script_runner.run(console_script, 'A', 'B', check=True)
    assert result.stdout == "['A', 'B']\n"
    with pytest.warns(match=r".*multiple arguments."):
        result = script_runner.run([console_script, 'C'], 'D', check=True)
    assert result.stdout == "['C', 'D']\n"


@pytest.mark.script_launch_mode('both')
def test_check(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    console_script.write_text("""import sys; sys.exit(1)""")
    with pytest.raises(CalledProcessError, match='.*non-zero exit status 1'):
        script_runner.run(str(console_script), check=True)


@pytest.mark.script_launch_mode('both')
def test_ignore_universal_newlines(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    expectation: dict[str, ContextManager[Any]] = {
        'inprocess': pytest.warns(match=r"Keyword argument .* was ignored"),
        'subprocess': contextlib.nullcontext(),
    }
    with expectation[script_runner.launch_mode]:
        result = script_runner.run(
            str(console_script), check=True, universal_newlines=True
        )
    assert result.stdout == 'foo\n'
    assert result.stderr == ''


@pytest.mark.script_launch_mode('subprocess')
def test_disable_universal_newlines(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    result = script_runner.run(
        str(console_script), check=True, universal_newlines=False
    )
    assert isinstance(result.stdout, bytes)
    assert isinstance(result.stderr, bytes)
    assert result.stdout.strip() == b'foo'
    assert result.stderr == b''


@pytest.mark.script_launch_mode('both')
def test_run_path(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    result = script_runner.run(console_script, check=True)
    assert result.stdout == 'foo\n'
    assert result.stderr == ''
    console_script.chmod(0o777)
    result = script_runner.run(console_script, check=True)
    assert result.stdout == 'foo\n'
    assert result.stderr == ''


@pytest.mark.script_launch_mode('both')
def test_run_script_codecs(
    console_script: Path, script_runner: ScriptRunner
) -> None:
    """Check that non-UTF-8 scripts can load"""
    console_script.write_text(
        """\
# -*- coding: cp437 -*-
import sys  # Non UTF-8 characters -> ≡≡≡
print('foo')
        """,
        encoding="cp437",
    )
    result = script_runner.run(console_script, check=True)
    assert result.stdout == 'foo\n'
    assert result.stderr == ''
