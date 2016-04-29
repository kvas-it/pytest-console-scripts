import pytest


def pytest_addoption(parser):
    group = parser.getgroup('console-scripts')
    group.addoption(
        '--script-launch-mode',
        metavar='inprocess|subprocess|both',
        action='store',
        dest='script_launch_mode',
        default=None,
        help='how to run python scripts under test (default: inprocess)'
    )
    parser.addini(
        'script_launch_mode',
        'how to run python scripts under test (inprocess|subprocess|both)'
    )


def pytest_generate_tests(metafunc):
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

    launch_mode_mark = getattr(metafunc.function, 'script_launch_mode', None)
    mark_mode = launch_mode_mark.args[0] if launch_mode_mark else None
    option_mode = metafunc.config.option.script_launch_mode
    config_mode = metafunc.config.getini('script_launch_mode')

    mode = mark_mode or option_mode or config_mode or 'inprocess'
    if mode in {'inprocess', 'subprocess'}:
        metafunc.parametrize('script_launch_mode', [mode])
    elif mode == 'both':
        metafunc.parametrize('script_launch_mode', ['inprocess', 'subprocess'])
    else:
        raise ValueError('Invalid script launch mode: {}'.format(mode))


class ScriptRunner(object):
    """Fixture for running python scripts under test."""

    def __init__(self, launch_mode, rootdir):
        assert launch_mode in {'inprocess', 'subprocess'}
        self.launch_mode = launch_mode
        self.rootdir = rootdir


@pytest.fixture
def script_launch_mode(request):
    return request.param


@pytest.fixture
def script_cwd(tmpdir):
    return tmpdir.join('script-cwd')


@pytest.fixture
def script_runner(script_cwd, script_launch_mode):
    return ScriptRunner(script_launch_mode, script_cwd)
