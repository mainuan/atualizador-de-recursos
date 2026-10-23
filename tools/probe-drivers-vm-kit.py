#!/usr/bin/python3
"""Homologa bytes, assinaturas e solver em APT isolado; nunca instala no anfitrião."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from drivers_vm import NAME, SHA, POLICY, dump, verify_kit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    kit = args.kit.resolve()
    metadata, _ = verify_kit(kit)
    tls = subprocess.check_output(['openssl', 'verify', '-x509_strict', '-verify_hostname',
        'homologacao.mainuan.test', '-CAfile', str(kit / 'tls/ca-teste.crt'), str(kit / 'tls/servidor.crt')], text=True)
    report = {'kit_id': metadata['id'], 'catalog_signature': True, 'apt_signatures': True,
              'official_deb_sha256': SHA, 'tls_chain': tls.strip(),
              'host_installations': 0, 'host_apt_configuration_modified': False,
              'real_vm_packagekit_policykit_tested': False}
    with tempfile.TemporaryDirectory(prefix='mainuan-gestor-apt-isolado-') as temporary:
        root = Path(temporary)
        for name in ('lists/partial', 'archives/partial', 'log', 'tmp', 'empty'):
            (root / name).mkdir(parents=True)
        # Cópia somente leitura do inventário do anfitrião. Não equivale ao inventário da VM.
        (root / 'status').write_bytes(Path('/var/lib/dpkg/status').read_bytes())
        (root / 'sources.list').write_text(f'deb [signed-by={kit}/repo-chave-teste.gpg] file:{kit}/apt ./\n')
        (root / 'preferences').write_text(POLICY)
        settings = {'Dir::Etc::main': '-', 'Dir::Etc::parts': str(root / 'empty'),
                    'Dir::Etc::sourcelist': str(root / 'sources.list'), 'Dir::Etc::sourceparts': '-',
                    'Dir::Etc::preferences': str(root / 'preferences'), 'Dir::Etc::preferencesparts': '-',
                    'Dir::State::status': str(root / 'status'), 'Dir::State::lists': str(root / 'lists'),
                    'Dir::State::extended_states': str(root / 'extended_states'),
                    'Dir::Cache::archives': str(root / 'archives'), 'Dir::Cache::pkgcache': str(root / 'pkgcache'),
                    'Dir::Cache::srcpkgcache': str(root / 'srcpkgcache'), 'Dir::Log': str(root / 'log')}
        config = root / 'apt.conf'
        config.write_text(''.join(f'{key} "{value}";\n' for key, value in settings.items()))
        env = dict(os.environ, APT_CONFIG=str(config), TMPDIR=str(root / 'tmp'), LC_ALL='C')
        sandbox = ['bwrap', '--unshare-user', '--unshare-net', '--ro-bind', '/', '/',
                   '--bind', str(root), str(root), '--proc', '/proc', '--dev', '/dev']

        def execute(argv, stdout_only=False):
            value = subprocess.run(sandbox + argv, env=env, check=True, capture_output=True, text=True, timeout=45)
            return value.stdout if stdout_only else value.stdout + value.stderr

        report['apt_update'] = execute(['apt-get', 'update'])
        report['apt_simulation'] = execute(['apt-get', '--simulate', '--no-remove', 'install', NAME + '=1.0'])
        changes = [line.split()[1] for line in report['apt_simulation'].splitlines() if line.startswith(('Inst ', 'Remv '))]
        assert changes == [NAME], changes
        source = '''import apt,json,sys
sys.path.insert(0,SRC)
from pathlib import Path
from mainuan_recursos.catalog import Config,authenticate
from mainuan_recursos.packages import build_plan
k=Path(KIT)
c=authenticate((k/'site/catalog/novidades.json').read_bytes(),(k/'site/catalog/novidades.json.sig').read_bytes(),Config.load(k/'config-homologacao.json'))
cache=apt.Cache()
p=cache[NAME]
plan=build_plan(c.releases[0],cache)
assert not plan.blockers and len(plan.pending)==1
assert p.candidate.version=='1.0' and p.candidate.sha256==SHA and any(o.trusted for o in p.candidate.origins)
p.mark_install(auto_fix=True,from_user=True)
assert [x.name for x in cache.get_changes()]==[NAME]
print(json.dumps({'trusted':True,'plan':[(r.name,r.status,r.candidate) for r in plan.rows],'changes':[x.name for x in cache.get_changes()]}))
'''.replace('SRC', repr(str(Path(__file__).resolve().parents[1] / 'src'))).replace('KIT', repr(str(kit))).replace('NAME', repr(NAME)).replace('SHA', repr(SHA))
        report['python_apt_plan'] = json.loads(execute(['/usr/bin/python3', '-c', source], stdout_only=True))
        # Introduz uma versão fictícia de uma dependência SOMENTE em índice temporário,
        # confiado apenas nesta raiz APT. O pin deve manter o pacote já instalado.
        adversarial = root / 'adversarial'; adversarial.mkdir()
        installed_version = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', 'ubuntu-drivers-common'], text=True)
        (adversarial / 'Packages').write_text('Package: ubuntu-drivers-common\nVersion: 999:999\nArchitecture: all\n'
            'Maintainer: Test <test@example.invalid>\nDescription: indice ficticio sem artefato\n'
            'Filename: inexistente.deb\nSize: 1\nSHA256: ' + '0' * 64 + '\n\n')
        with (root / 'sources.list').open('a') as stream:
            stream.write(f'deb [trusted=yes] file:{adversarial} ./\n')
        execute(['apt-get', 'update'])  # trusted=yes restrito ao índice adversarial descartável, jamais no kit.
        report['apt_with_new_driver_dependency_version'] = execute(['apt-get', '--simulate', '--no-remove', 'install', NAME + '=1.0'])
        assert [line.split()[1] for line in report['apt_with_new_driver_dependency_version'].splitlines()
                if line.startswith(('Inst ', 'Remv '))] == [NAME]
        report['dependency_upgrade_blocked'] = True
        report['existing_dependency_version_in_host_copy'] = installed_version
        # Retira a dependência da CÓPIA do status. A operação precisa falhar sem instalá-la.
        status = (root / 'status').read_text()
        (root / 'status').write_text('\n\n'.join(stanza for stanza in status.split('\n\n')
                                      if not stanza.startswith('Package: ubuntu-drivers-common\n')))
        failed = subprocess.run(sandbox + ['apt-get', '--simulate', '--no-remove', 'install', NAME + '=1.0'],
                                env=env, capture_output=True, text=True, timeout=30)
        if failed.returncode == 0:
            raise RuntimeError('Dependência ausente não bloqueou a simulação:\n' + failed.stdout + failed.stderr)
        report['missing_dependency_blocked'] = True
        report['missing_dependency_output'] = failed.stdout + failed.stderr
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dump(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if 'simulation' not in k and 'output' not in k and not k.startswith('apt_')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
