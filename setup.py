import os
from setuptools import setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    with open(file_path, encoding='utf-8') as f:
        return f.read()


setup(
    name='pytest-console-scripts',
    use_scm_version=True,
    author='Vasily Kuznetsov',
    author_email='kvas.it@gmail.com',
    maintainer='Vasily Kuznetsov',
    maintainer_email='kvas.it@gmail.com',
    license='MIT',
    url='https://github.com/kvas-it/pytest-console-scripts',
    description='Pytest plugin for testing console scripts',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    py_modules=['pytest_console_scripts'],
    install_requires=['pytest>=4.0.0'],
    python_requires='>=3.6',
    setup_requires=['setuptools-scm'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
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
