from __future__ import annotations

import contextlib
import io
import logging
import os
import shlex
import shutil
import subprocess
import sys
import traceback
import warnings
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence, Union
from unittest import mock

import pytest

if sys.version_info < (3, 10):
    import importlib_metadata
else:
    import importlib.metadata as importlib_metadata

_StrOrPath = Union[str, os.PathLike]
"""A command line argument type as a str or path."""

_Command = Union[_StrOrPath, Sequence[_StrOrPath]]
"""A command-like type compatible with subprocess.run."""

StreamMock = io.StringIO


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('console-scripts')
    group.addoption(
        '--script-launch-mode',
        metavar='inprocess|subprocess|both',
        action='store',
        dest='script_launch_mode',
        default=None,
        help='how to run python scripts under test (default: inprocess)'
    )
    group.addoption(
        '--hide-run-results',
        action='store_true',
        dest='hide_run_results',
        default=False,
        help="don't print out script run results on failures or when "
             'output capturing is disabled'
    )
    parser.addini(
        'script_launch_mode',
        'how to run python scripts under test (inprocess|subprocess|both)'
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        'markers',
        'script_launch_mode: how to run python scripts under test '
        '(inprocess|subprocess|both)',
    )


def _get_mark_mode(metafunc: pytest.Metafunc) -> str | None:
    """Return launch mode as indicated by test function marker or None."""
    marker = metafunc.definition.get_closest_marker('script_launch_mode')
    if marker:
        return str(marker.args[0])
    return None


def _is_nonexecutable_python_file(command: _StrOrPath) -> bool:
    """Check if `command` is a Python file with no executable mode set."""
    command = Path(command)
    mode = command.stat().st_mode
    if mode & os.X_OK:
        return False
    return command.suffix == '.py'


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize script_launch_mode fixture.

    Checks the configuration sources in this order:
    - `script_launch_mode` mark on the test,
    - `--script-launch-mode` option,
    - `script_launch_mode` configuration option in [pytest] section of the
      pyest config file.

    This process yields a value that can be one of:
    - "inprocess" -- The script will be run via loading its main function
      into the test runner process and mocking the environment.
    - "subprocess" -- The script will be run via `subprocess` module.
    - "both" -- The test will be run twice: once in inprocess mode and once
      in subprocess mode.
    - None -- Same as "inprocess".
    """
    if 'script_launch_mode' not in metafunc.fixturenames:
        return

    mark_mode = _get_mark_mode(metafunc)
    option_mode = metafunc.config.option.script_launch_mode
    config_mode = metafunc.config.getini('script_launch_mode')

    mode = mark_mode or option_mode or config_mode or 'inprocess'

    if mode in {'inprocess', 'subprocess'}:
        metafunc.parametrize('script_launch_mode', [mode], indirect=True)
    elif mode == 'both':
        metafunc.parametrize('script_launch_mode', ['inprocess', 'subprocess'],
                             indirect=True)
    else:
        raise ValueError(f'Invalid script launch mode: {mode}')


class RunResult:
    """Result of running a script."""

    def __init__(
        self, returncode: int, stdout: str, stderr: str, print_result: bool
    ) -> None:
        self.success = returncode == 0
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        if print_result:
            self.print()

    def print(self) -> None:
        print('# Script return code:', self.returncode)
        print('# Script stdout:', self.stdout, sep='\n')
        print('# Script stderr:', self.stderr, sep='\n')


def _handle_command_args(
    command: _Command,
    *args: _StrOrPath,
    shell: bool = False,
    stacklevel: int = 1,
) -> Sequence[_StrOrPath]:
    """Return command arguments in a consistent list format.

    If shell=True then this function tries to mimic local shell execution.
    """
    if shell:
        if args or not isinstance(command, (str, os.PathLike)):
            command = subprocess.list2cmdline(
                str(arg)
                for arg in _handle_command_args(
                    command, *args, shell=False, stacklevel=stacklevel + 1
                )
            )
        command = shlex.split(str(command), posix=os.name == 'posix')
        args = ()

    if args:
        warnings.warn(
            'script_runner commands should be passed as a single sequence,'
            ' not as multiple arguments.'
            '\nReplace `script_runner.run(a, b, c)` calls with'
            ' `script_runner.run([a, b, c])`',
            DeprecationWarning,
            stacklevel=stacklevel + 1,
        )
        if not isinstance(command, (str, os.PathLike)):
            return [*command, *args]
        return [command, *args]
    if isinstance(command, (str, os.PathLike)):
        return [command]
    return command


@contextlib.contextmanager
def _patch_environ(new_environ: dict[str, str] | None) -> Iterator[None]:
    """Replace the environment for the duration of a context."""
    if new_environ is None:
        yield
        return
    old_environ = os.environ.copy()
    os.environ.clear()
    os.environ.update(new_environ)
    yield
    os.environ.clear()
    os.environ.update(old_environ)


@contextlib.contextmanager
def _chdir_context(new_dir: _StrOrPath | None) -> Iterator[None]:
    """Replace the current directory for the duration of a context."""
    if new_dir is None:
        yield
        return
    old_cwd = os.getcwd()
    os.chdir(new_dir)
    yield
    os.chdir(old_cwd)


@contextlib.contextmanager
def _push_and_reset_logger() -> Iterator[None]:
    """Do a very basic reset of the root logger and restore its config on exit.

    This allows scripts to call logging.basicConfig(...) and have
    it work as expected. It might not work for more sophisticated logging
    setups but it's simple and covers the basic usage whereas implementing
    a comprehensive fix is impossible in a compatible way.
    """
    logger = logging.getLogger()
    old_handlers = logger.handlers
    old_disabled = logger.disabled
    old_level = logger.level
    logger.handlers = []
    logger.disabled = False
    logger.setLevel(logging.NOTSET)
    yield
    # Restore logger to previous configuration
    logger.handlers = old_handlers
    logger.disabled = old_disabled
    logger.setLevel(old_level)


class ScriptRunner:
    """Fixture for running python scripts under test."""

    def __init__(
        self, launch_mode: str,
        rootdir: _StrOrPath,
        print_result: bool = True
    ) -> None:
        assert launch_mode in {'inprocess', 'subprocess'}
        self.launch_mode = launch_mode
        self.print_result = print_result
        self.rootdir = rootdir

    def __repr__(self) -> str:
        return f'<ScriptRunner {self.launch_mode}>'

    def run(
        self,
        command: _Command,
        *arguments: _StrOrPath,
        print_result: bool | None = None,
        shell: bool = False,
        cwd: _StrOrPath | None = None,
        env: dict[str, str] | None = None,
        stdin: io.IOBase | None = None,
        check: bool = False,
        **options: Any,
    ) -> RunResult:
        if print_result is None:
            print_result = self.print_result

        if print_result:
            print('# Running console script:', command, *arguments)

        if self.launch_mode == 'inprocess':
            run_function = self.run_inprocess
        else:
            run_function = self.run_subprocess
        return run_function(
            command,
            *arguments,
            print_result=print_result,
            shell=shell,
            cwd=cwd,
            env=env,
            stdin=stdin,
            check=check,
            _stacklevel=2,
            **options,
        )

    @staticmethod
    def _locate_script(
        command: _StrOrPath,
        *,
        cwd: _StrOrPath | None,
        env: dict[str, str] | None,
    ) -> Path:
        """Locate script in PATH or in current directory."""
        script_path = shutil.which(
            command,
            path=env.get('PATH', None) if env is not None else None,
        )
        if script_path is not None:
            return Path(script_path)

        cwd = cwd if cwd is not None else os.getcwd()
        return Path(cwd, command).resolve(strict=True)

    @classmethod
    def _load_script(
        cls,
        command: _StrOrPath,
        *,
        cwd: _StrOrPath | None,
        env: dict[str, str] | None,
    ) -> Callable[[], int | None]:
        """Load target script via entry points or compile/exec."""
        if isinstance(command, str):
            entry_points = tuple(
                importlib_metadata.entry_points(
                    group='console_scripts', name=command
                )
            )
            if entry_points:
                def console_script() -> int | None:
                    s: Callable[[], int | None] = entry_points[0].load()
                    return s()
                return console_script

        script_path = cls._locate_script(command, cwd=cwd, env=env)

        def exec_script() -> int:
            compiled = compile(
                script_path.read_bytes(), str(script_path), 'exec', flags=0
            )
            exec(compiled, {'__name__': '__main__'})
            return 0

        return exec_script

    @classmethod
    def run_inprocess(
        cls,
        command: _Command,
        *arguments: _StrOrPath,
        shell: bool = False,
        cwd: _StrOrPath | None = None,
        env: dict[str, str] | None = None,
        print_result: bool = True,
        stdin: io.IOBase | None = None,
        check: bool = False,
        _stacklevel: int = 1,
        **options: Any,
    ) -> RunResult:
        for key in options:
            warnings.warn(
                f'Keyword argument {key!r} was ignored.'
                '\nConsider using subprocess mode or raising an issue.',
                stacklevel=_stacklevel + 1,
            )
        cmd_args = _handle_command_args(
            command, *arguments, shell=shell, stacklevel=_stacklevel + 1
        )
        script = cls._load_script(cmd_args[0], cwd=cwd, env=env)
        cmd_args = [str(cmd) for cmd in cmd_args]
        stdin_stream = stdin if stdin is not None else StreamMock()
        stdout_stream = StreamMock()
        stderr_stream = StreamMock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch('sys.stdin', new=stdin_stream))
            stack.enter_context(contextlib.redirect_stdout(stdout_stream))
            stack.enter_context(contextlib.redirect_stderr(stderr_stream))
            stack.enter_context(mock.patch('sys.argv', new=cmd_args))
            stack.enter_context(_push_and_reset_logger())
            stack.enter_context(_patch_environ(env))
            stack.enter_context(_chdir_context(cwd))

            try:
                returncode = script()
            except SystemExit as exc:
                returncode = 1
                if isinstance(exc.code, str):
                    stderr_stream.write(f'{exc}\n')
                    returncode = 1
                else:
                    returncode = exc.code
            except Exception:
                returncode = 1
                try:
                    et, ev, tb = sys.exc_info()
                    assert tb
                    # Hide current frame from the stack trace.
                    traceback.print_exception(et, ev, tb.tb_next)
                finally:
                    del tb

        result = RunResult(
            returncode or 0,  # None also means success
            stdout_stream.getvalue(),
            stderr_stream.getvalue(),
            print_result,
        )

        if check and returncode:
            raise subprocess.CalledProcessError(
                returncode,
                cmd_args,
                result.stdout,
                result.stderr,
            )

        return result

    @classmethod
    def run_subprocess(
        cls,
        command: _Command,
        *arguments: _StrOrPath,
        print_result: bool = True,
        shell: bool = False,
        cwd: _StrOrPath | None = None,
        env: dict[str, str] | None = None,
        stdin: io.IOBase | None = None,
        check: bool = False,
        universal_newlines: bool = True,
        _stacklevel: int = 1,
        **options: Any,
    ) -> RunResult:
        stdin_input: str | bytes | None = None
        if stdin is not None:
            stdin_input = stdin.read()

        script_path = cls._locate_script(
            _handle_command_args(
                command, *arguments, shell=shell, stacklevel=_stacklevel + 1
            )[0],
            cwd=cwd,
            env=env,
        )
        if arguments:
            command = _handle_command_args(
                command, *arguments, shell=shell, stacklevel=_stacklevel + 1
            )

        if _is_nonexecutable_python_file(script_path):
            command = _handle_command_args(
                command, shell=shell, stacklevel=_stacklevel + 1
            )
            command = [sys.executable or 'python', *command]

        try:
            cp = subprocess.run(
                command,
                input=stdin_input,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=shell,
                cwd=cwd,
                env=env,
                check=check,
                universal_newlines=universal_newlines,
                **options,
            )
        except subprocess.CalledProcessError as exc:
            RunResult(exc.returncode, exc.stdout, exc.stderr, print_result)
            raise
        return RunResult(cp.returncode, cp.stdout, cp.stderr, print_result)


@pytest.fixture
def script_launch_mode(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def script_cwd(tmp_path: Path) -> Path:
    work_dir = tmp_path / 'script-cwd'
    work_dir.mkdir()
    return work_dir


@pytest.fixture
def script_runner(
    request: pytest.FixtureRequest, script_cwd: Path, script_launch_mode: str
) -> ScriptRunner:
    print_result = not request.config.getoption('--hide-run-results')
    return ScriptRunner(script_launch_mode, script_cwd, print_result)
