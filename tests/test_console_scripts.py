from __future__ import print_function

import pytest


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


@pytest.fixture(params=[None, 'inprocess', 'subprocess', 'both'])
def launch_mode_conf(request):
    return request.param


@pytest.fixture
def launch_modes(launch_mode_conf):
    if launch_mode_conf == 'both':
        return {'inprocess', 'subprocess'}
    elif launch_mode_conf is not None:
        return {launch_mode_conf}
    else:
        return {'inprocess'}  # Default value.


CHECK_LAUNCH_MODE = """
def test_launch_mode(script_runner):
    assert script_runner.launch_mode in {}
"""


def test_command_line_option(run_test, launch_mode_conf, launch_modes):
    """Make sure that script launch mode is set from command line."""
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


def test_help_message(testdir):
    result = testdir.runpytest(
        '--help',
    )
    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines([
        'console-scripts:',
        '*--script-launch-mode=*',
    ])
