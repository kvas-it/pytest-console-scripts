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
        'how to run python scripts under test (inprocess/subprocess/both)'
    )


def pytest_generate_tests(metafunc):
    """Parametrize script_launch_mode fixture."""
    if 'script_launch_mode' not in metafunc.fixturenames:
        return

    opt_mode = metafunc.config.option.script_launch_mode
    conf_mode = metafunc.config.getini('script_launch_mode')
    mode = opt_mode or conf_mode or 'inprocess'
    if mode in {'inprocess', 'subprocess'}:
        metafunc.parametrize('script_launch_mode', [mode])
    elif mode == 'both':
        metafunc.parametrize('script_launch_mode', ['inprocess', 'subprocess'])
    else:
        raise ValueError('Invalid script launch mode: {}'.format(mode))


class ScriptRunner(object):
    """Fixture for running python scripts under test."""

    def __init__(self, launch_mode, rootdir):
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
