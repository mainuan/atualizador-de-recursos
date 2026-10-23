#!/usr/bin/python3
"""Valida catálogo/índices APT fictícios usando APT real em sandbox, sem instalação."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from mainuan_recursos.catalog import Config, authenticate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('demo', type=Path, help='saída de demo-publication.py')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    demo = args.demo.resolve()
    metadata = json.loads((demo / 'resultado.json').read_text())
    if metadata.get('test_only') is not True:
        raise ValueError('Apenas publicações fictícias são aceitas.')
    config = Config.load(demo / 'config-teste.json')
    report = {'test_only': True, 'host_installations': 0, 'host_configuration_modified': False, 'editions': []}
    for stage in (1, 2):
        edition = demo / f'edicao-{stage}'
        directory = edition / 'catalogo'
        catalog = authenticate((directory / 'novidades.json').read_bytes(),
                               (directory / 'novidades.json.sig').read_bytes(), config)
        # Os nomes validados do catálogo vão para argv depois de --, jamais para um shell.
        packages = catalog.releases[0].packages
        if not all(p.name.startswith('mainuan-dados-ficticios-') for p in packages):
            raise ValueError('Pacotes fora da homologação fictícia.')
        with tempfile.TemporaryDirectory(prefix='mainuan-publicacao-apt-') as temp:
            root = Path(temp)
            for name in ('lists/partial', 'archives/partial', 'log', 'tmp', 'conf.d'):
                (root / name).mkdir(parents=True)
            (root / 'status').write_text('')
            (root / 'sources.list').write_text(
                f'deb [signed-by={demo}/apt-chave-teste.gpg] file:{edition}/apt ./\n')
            settings = {'Dir::Etc::main': '-', 'Dir::Etc::parts': str(root / 'conf.d'),
                        'Dir::Etc::sourcelist': str(root / 'sources.list'), 'Dir::Etc::sourceparts': '-',
                        'Dir::State::status': str(root / 'status'), 'Dir::State::lists': str(root / 'lists'),
                        'Dir::State::extended_states': str(root / 'extended_states'),
                        'Dir::Cache::archives': str(root / 'archives'), 'Dir::Cache::pkgcache': '',
                        'Dir::Cache::srcpkgcache': '', 'Dir::Log': str(root / 'log')}
            apt_config = root / 'apt.conf'
            apt_config.write_text(''.join(f'{key} "{value}";\n' for key, value in settings.items()))
            env = dict(os.environ, APT_CONFIG=str(apt_config), TMPDIR=str(root / 'tmp'), LC_ALL='C')
            sandbox = ['bwrap', '--unshare-user', '--unshare-net', '--ro-bind', '/', '/',
                       '--bind', temp, temp, '--proc', '/proc', '--dev', '/dev']
            update = subprocess.run(sandbox + ['apt-get', 'update'], env=env, capture_output=True,
                                    text=True, check=True, timeout=30)
            simulation = subprocess.run(sandbox + ['apt-get', '--simulate', '--no-remove', 'install', '--',
                                       *(p.name + '=' + p.min_version for p in packages)], env=env,
                                       capture_output=True, text=True, check=True, timeout=30)
            probe = '''import apt,json,sys
from pathlib import Path
sys.path.insert(0, SRC)
from mainuan_recursos.catalog import Config,authenticate
from mainuan_recursos.packages import build_plan
root=__import__('pathlib').Path(EDITION)/'catalogo'
cat=authenticate((root/'novidades.json').read_bytes(),(root/'novidades.json.sig').read_bytes(),Config.load(Path(CONFIG)))
cache=apt.Cache()
plan=build_plan(cat.releases[0],cache)
assert not plan.blockers and len(plan.pending)==3
print(json.dumps([{'package':r.name,'version':r.candidate,'architecture':r.architecture,'sha256':r.sha256,'installed':r.installed,'status':r.status} for r in plan.rows]))
'''.replace('SRC', repr(str(Path(__file__).resolve().parents[1] / 'src'))).replace('EDITION', repr(str(edition))).replace('CONFIG', repr(str(demo / 'config-teste.json')))
            result = subprocess.run(sandbox + ['/usr/bin/python3', '-c', probe], env=env,
                                    capture_output=True, text=True, check=True, timeout=30)
            report['editions'].append({'sequence': catalog.sequence, 'apt_update_code': update.returncode,
                                       'apt_solver_code': simulation.returncode, 'plan': json.loads(result.stdout),
                                       'status_unchanged': (root / 'status').read_text() == ''})
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
