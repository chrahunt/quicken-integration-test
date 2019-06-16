from setuptools import find_packages, setup


setup(
    name='quicken-integration-test',
    version='0.1.0',

    entry_points={
        'console_scripts': ['quicken-integration-test=quicken_integration_test.cli:cli'],
    },
    packages=find_packages(),
    setup_requires=[
        'importlib_metadata',
    ],
)
