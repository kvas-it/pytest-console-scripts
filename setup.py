import io
import os
from setuptools import setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return io.open(file_path, encoding='utf-8').read()


setup(
    name='pytest-console-scripts',
    version='0.2.0',
    author='Vasily Kuznetsov',
    author_email='kvas.it@gmail.com',
    maintainer='Vasily Kuznetsov',
    maintainer_email='kvas.it@gmail.com',
    license='MIT',
    url='https://github.com/kvas-it/pytest-console-scripts',
    description='Pytest plugin for testing console scripts',
    long_description=read('README.rst'),
    py_modules=['pytest_console_scripts'],
    install_requires=['pytest>=4.0.0', 'mock>=2.0.0', 'pytest-runner'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
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
    test_suite='tests',
    tests_require=['pytest', 'virtualenv', 'mock'],
)
