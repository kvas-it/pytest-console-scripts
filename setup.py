from pathlib import Path
from setuptools import setup

THIS_DIR = Path(__file__).parent
README_TEXT = (THIS_DIR / 'README.md').read_text(encoding='utf-8')


setup(
    name='pytest-console-scripts',
    use_scm_version=True,
    author='Vasily Kuznetsov',
    author_email='kvas.it@gmail.com',
    maintainer='Vasily Kuznetsov, Kyle Benesch',
    maintainer_email='kvas.it@gmail.com, 4b796c65+github@gmail.com',
    license='MIT',
    url='https://github.com/kvas-it/pytest-console-scripts',
    description='Pytest plugin for testing console scripts',
    long_description=README_TEXT,
    long_description_content_type='text/markdown',
    packages=['pytest_console_scripts'],
    package_data={'pytest_console_scripts': ['py.typed']},
    install_requires=[
        'pytest >=4.0.0',
        "importlib_metadata >=3.6; python_version < '3.10'",
    ],
    python_requires='>=3.8',
    setup_requires=['setuptools-scm'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
    ],
    entry_points={
        'pytest11': [
            'console-scripts = pytest_console_scripts',
        ],
    },
)
