from __future__ import print_function, unicode_literals

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
    def run(script, passed=1, skipped=0, failed=0, launch_mode_conf=None):
        testdir.makepyfile(script)
        args = []
        if launch_mode_conf is not None:
            args.append('--script-launch-mode=' + launch_mode_conf)
        result = testdir.runpytest(*args)
        print('\n'.join(['pytest stdout:'] + result.outlines +
                        ['pytest stderr:'] + result.errlines))
        result.assert_outcomes(passed=passed, skipped=skipped, failed=failed)
        return result
    return run


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
        '*--hide-run-results*',
    ])
