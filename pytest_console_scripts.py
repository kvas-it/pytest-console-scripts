import pytest


def pytest_addoption(parser):
    group = parser.getgroup('console-scripts')
    group.addoption(
        '--script-launch-mode',
        action='store',
        dest='script_launch_mode',
        default='inprocess',
        help='Should the scripts be run "inprocess" or as a "subprocess".'
    )

    parser.addini(
        'script-launch-mode',
        'Should the scripts be run "inprocess" or as a "subprocess".'
    )


@pytest.fixture
def script_runner(request):
    return request.config.option.script_launch_mode
