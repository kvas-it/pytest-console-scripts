from __future__ import annotations

import pytest


@pytest.fixture(params=[None, 'inprocess', 'subprocess', 'both'])
def launch_mode_conf(request: pytest.FixtureRequest) -> str | None:
    """Configured launch mode (None|'inprocess'|'subprocess'|'both')."""
    assert request.param is None or isinstance(request.param, str)
    return request.param


@pytest.fixture
def launch_modes(launch_mode_conf: str | None) -> set[str]:
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


class RunTest:
    def __init__(self, testdir: pytest.Testdir) -> None:
        self.testdir = testdir

    def __call__(
        self,
        script: str,
        passed: int = 1,
        skipped: int = 0,
        failed: int = 0,
        launch_mode_conf: str | None = None
    ) -> pytest.RunResult:
        self.testdir.makepyfile(script)
        args = []
        if launch_mode_conf is not None:
            args.append('--script-launch-mode=' + launch_mode_conf)
        result = self.testdir.runpytest(*args)
        print('\n'.join(['pytest stdout:'] + result.outlines +
                        ['pytest stderr:'] + result.errlines))
        result.assert_outcomes(passed=passed, skipped=skipped, failed=failed)
        return result


@pytest.fixture
def run_test(testdir: pytest.Testdir) -> RunTest:
    return RunTest(testdir)


CHECK_LAUNCH_MODE = """
def test_both(script_runner, accumulator=set()):
    assert script_runner.launch_mode in {}
    assert script_runner.launch_mode not in accumulator
    accumulator.add(script_runner.launch_mode)
"""


def test_command_line_option(
    run_test: RunTest, launch_mode_conf: str | None, launch_modes: set[str]
) -> None:
    run_test(
        CHECK_LAUNCH_MODE.format(launch_modes),
        passed=len(launch_modes),
        launch_mode_conf=launch_mode_conf
    )


def test_config_option(
    run_test: RunTest,
    testdir: pytest.Testdir,
    launch_mode_conf: str | None,
    launch_modes: set[str],
) -> None:
    if launch_mode_conf is not None:
        testdir.makeini(f"""
            [pytest]
            script_launch_mode = {launch_mode_conf}
        """)

    run_test(
        CHECK_LAUNCH_MODE.format(launch_modes),
        passed=len(launch_modes)
    )


def test_override_launch_mode_with_mark(
    run_test: RunTest, launch_mode_conf: str | None
) -> None:
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


def test_help_message(testdir: pytest.Testdir) -> None:
    result = testdir.runpytest(
        '--help',
    )
    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines([
        'console-scripts:',
        '*--script-launch-mode=*',
        '*--hide-run-results*',
    ])


def test_script_runner_factory(script_runner_factory, script_cwd) -> None:
    runner = script_runner_factory.make_runner('inprocess')
    assert runner.launch_mode == 'inprocess'
    assert runner.rootdir == script_cwd


def test_script_runner_factory_scope(run_test: RunTest) -> None:
    run_test(
        """
import pytest

_heavy_create_count = 0

@pytest.fixture(autouse=True, scope="session")
def heavy_fixture(script_runner_factory):
    global _heavy_create_count
    _heavy_create_count += 1
    return _heavy_create_count

@pytest.mark.script_launch_mode('inprocess')
def test_inprocess(heavy_fixture):
    assert heavy_fixture == 1

@pytest.mark.script_launch_mode('subprocess')
def test_subprocess(heavy_fixture):
    assert heavy_fixture == 1

@pytest.mark.script_launch_mode('both')
def test_both(script_runner, heavy_fixture, accumulator=set()):
    assert heavy_fixture == 1
        """,
        passed=4,
    )
