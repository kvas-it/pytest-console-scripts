# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed
- Dropped support for Python 3.7
  [#72](https://github.com/kvas-it/pytest-console-scripts/pull/72)

### Fixed
- Fix loading scripts with non-UTF-8 encodings.
  [#77](https://github.com/kvas-it/pytest-console-scripts/pull/77)
- Print output when a subprocess runner with `check=True` fails was missing.
  [#78](https://github.com/kvas-it/pytest-console-scripts/pull/78)

## [1.4.0] - 2023-05-22

### Added
- Added type-hinting for all types, `pytest_console_scripts.ScriptRunner`
  can now be used to hint the `script_runner` fixture.
  [#62](https://github.com/kvas-it/pytest-console-scripts/pull/62)
- Added support for the `shell` and `check` keywords for in-process mode.
  These behave as similarly to `subprocess.run` as possible.
- Script runners now take command arguments similar to `subprocess.run`,
  including support for PathLike objects.
  [#69](https://github.com/kvas-it/pytest-console-scripts/pull/69)

### Deprecated
- Passing command arguments in `*args` is now deprecated and will raise warnings.
  These should be wrapped in a list or tuple from now on, similar to `subprocess.run`.
  [#69](https://github.com/kvas-it/pytest-console-scripts/pull/69)

### Removed
- Dropped support for Python 3.6
  [#61](https://github.com/kvas-it/pytest-console-scripts/pull/61)

### Fixed
- Install-time dependencies have been fixed.
  [#56](https://github.com/kvas-it/pytest-console-scripts/issues/56)

## [1.3.1] - 2022-03-18

### Changed
- Removed `mock` dependency.
  [#53](https://github.com/kvas-it/pytest-console-scripts/pull/53)

## [1.3.0] - 2022-02-23

### Changed
- Added `python_requires` to the project.
  [#51](https://github.com/kvas-it/pytest-console-scripts/issues/51)

## [1.2.2] - 2022-01-06

### Added
- Add `print` method to allow results to be manually printed.
  [#49](https://github.com/kvas-it/pytest-console-scripts/issues/49)

### Fixed
- Avoid overwriting the global logging config of tested scripts.
  [#48](https://github.com/kvas-it/pytest-console-scripts/pull/48)

## [1.2.1] - 2021-09-28

### Removed
- Drop support for Python 3.5

## [1.2.0] - 2021-04-26

### Changed
- Locate the Python interpreter through sys.executable

### Fixed
- Do not rely on the Python interpreter being called `python`,
  as that command does not exist in certain environments.

## [1.1.0] - 2020-11-20

### Added
- Add option to suppress printing script run results.
  [#41](https://github.com/kvas-it/pytest-console-scripts/issues/41)

## [1.0.0] - 2020-10-06

### Added
- Support scripts that are not in `console_scripts`.
  [#17](https://github.com/kvas-it/pytest-console-scripts/issues/17)
