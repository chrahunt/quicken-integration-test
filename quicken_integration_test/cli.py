import argparse
import json
import subprocess
import sys
import tempfile
import textwrap
import timeit

from collections import namedtuple
from pathlib import Path
from typing import List


Entrypoint = namedtuple('Entrypoint', 'name old_name spec control')


def make_ep_spec(prefix, script_name, entrypoint, control_ep) -> Entrypoint:
    """
    Args:
        prefix: prefix for command
        script_name: quicken script name
        entrypoint: dict with
            attrs: list of strings referring to the nested attribute entrypoint
            module_name: the string name of the module to import
    Returns:
    """
    attrs = '.'.join(entrypoint['attrs'])
    module_name = entrypoint['module_name']
    name = entrypoint['name']
    new_name = f'{prefix}_{name}'
    spec = f'{script_name}:{module_name}._.{attrs}'
    return Entrypoint(new_name, name, spec, control_ep)


def make_quicken_ep_specs(entrypoint):
    ctl_ep = make_ep_spec('qkc', 'quicken.ctl_script', entrypoint, None)
    return [
        make_ep_spec('qk', 'quicken.script', entrypoint, ctl_ep),
        ctl_ep,
    ]


def install_project(env, dependencies: List[str], entrypoints: List[Entrypoint]):
    console_scripts = [f'{ep.name}={ep.spec}' for ep in entrypoints]
    setup_py = textwrap.dedent(f'''
    from setuptools import setup

    setup(
        name="quicken-test",
        version="0.1.0",

        install_requires={dependencies!r},
        entry_points={{
            'console_scripts': [{console_scripts!r}],
        }}
    )
    ''')

    d = tempfile.mkdtemp()
    f = Path(d) / 'setup.py'
    f.write_text(setup_py, encoding='utf-8')
    # Force PEP-517 so a wheel gets built and we get an efficient entrypoint.
    f2 = Path(d) / 'pyproject.toml'
    pyproject_toml = '''
    [build-system]
    requires = ["setuptools", "wheel"]
    '''
    f2.write_text(pyproject_toml, encoding='utf-8')
    env.install(d)


def time_action(cmd, *args, **kwargs):
    with tempfile.TemporaryDirectory() as d:
        #output_file = Path(d) / 'output.txt'
        #new_cmd = [
        #    '/usr/bin/time',
        #    '-a',
        #    '-o', output_file,
        #    '-f', '%e',
        #]
        #new_cmd.extend(cmd)
        start = timeit.default_timer()
        result = subprocess_run(cmd, *args, **kwargs)
        end = timeit.default_timer()
        elapsed_time = end - start
        result.duration = elapsed_time
    return result


def subprocess_run(*args, **kwargs):
    result = subprocess.run(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    result.stdout = result.stdout.decode('utf-8')
    result.stderr = result.stderr.decode('utf-8')
    return result


def main():
    sys.exit(cli(sys.argv[1:]))


class Venv:
    def install(self, *args):
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', *args])
        assert result.returncode == 0


def cli():
    parser = argparse.ArgumentParser(description='Run quicken-related tests')
    parser.add_argument('--entrypoints', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()

    with open(args.entrypoints) as f:
        entrypoints = json.load(f)

    output = open(args.output, 'w', encoding='utf-8')

    for package in entrypoints:
        name = package['name']
        version = package['version']
        new_eps = []
        eps = package['entrypoints']
        for ep in eps:
            new_eps.extend(make_quicken_ep_specs(ep))
        # TODO: In virtual environment.
        fake_venv = Venv()

        install_project(fake_venv, [f'{name}=={version}'], new_eps)
        output_data = {
            'name': name,
            'version': version,
        }

        script_eps = [ep for ep in new_eps if ep.control is not None]
        for ep in script_eps:
            this_output_data = {
                'command': ep.old_name,
            }
            # Test times.
            result = subprocess_run([ep.old_name, '--help'])
            this_output_data['original_rc'] = result.returncode
            this_output_data['original_stderr'] = result.stderr
            this_output_data['original_stdout'] = result.stdout
            result = time_action([ep.old_name, '--help'])
            this_output_data['original_2_rc'] = result.returncode
            this_output_data['original_2_stderr'] = result.stderr
            this_output_data['original_2_stdout'] = result.stdout
            this_output_data['original_duration'] = result.duration

            result = subprocess_run([ep.name, '--help'])
            this_output_data['quicken_rc'] = result.returncode
            this_output_data['quicken_stderr'] = result.stderr
            this_output_data['quicken_stdout'] = result.stdout
            result = time_action([ep.name, '--help'])
            this_output_data['quicken_2_rc'] = result.returncode
            this_output_data['quicken_2_stderr'] = result.stderr
            this_output_data['quicken_2_stdout'] = result.stdout
            this_output_data['quicken_duration'] = result.duration

            control_ep = ep.control
            result = subprocess_run([control_ep.name, 'status'])
            this_output_data['ctl_status_rc'] = result.returncode
            this_output_data['ctl_status_stderr'] = result.stderr
            this_output_data['ctl_status_stdout'] = result.stdout
            result = subprocess_run([control_ep.name, 'stop'])
            this_output_data['ctl_stop_rc'] = result.returncode
            this_output_data['ctl_stop_stderr'] = result.stderr
            this_output_data['ctl_stop_stdout'] = result.stdout

            json.dump(
                {
                    **this_output_data,
                    **output_data
                },
                output,
                separators=(',', ':'),
            )
            output.write('\n')
