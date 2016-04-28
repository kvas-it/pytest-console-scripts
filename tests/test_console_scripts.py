def test_script_runner_fixture(testdir):
    """Make sure that pytest accepts our fixture."""

    # create a temporary pytest test module
    testdir.makepyfile("""
        def test_sth(script_runner):
            assert script_runner == "subprocess"
    """)

    # run pytest with the following cmd args
    result = testdir.runpytest(
        '--script-launch-mode=subprocess',
        '-v'
    )

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines([
        '*::test_sth PASSED',
    ])

    # make sure that that we get a '0' exit code for the testsuite
    assert result.ret == 0


def test_help_message(testdir):
    result = testdir.runpytest(
        '--help',
    )
    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines([
        'console-scripts:',
        '*--script-launch-mode=*',
    ])


def test_hello_ini_setting(testdir):
    testdir.makeini("""
        [pytest]
        script-launch-mode = subprocess
    """)

    testdir.makepyfile("""
        import pytest

        @pytest.fixture
        def hello(request):
            return request.config.getini('script-launch-mode')

        def test_script_launch_mode(hello):
            assert hello == 'subprocess'
    """)

    result = testdir.runpytest('-v')

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines([
        '*::test_script_launch_mode PASSED',
    ])

    # make sure that that we get a '0' exit code for the testsuite
    assert result.ret == 0
