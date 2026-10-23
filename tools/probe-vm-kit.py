#!/usr/bin/python3
"""Valida assinatura, payload e índices APT do kit sem instalar pacotes."""
import argparse
import hashlib
import fcntl
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import io

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mainuan_recursos.catalog import Config, authenticate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    opts=parser.parse_args()
    kit=opts.kit.resolve()
    report={'test_only':True,'host_installations':0,'host_apt_configuration_modified':False}
    config=Config.load(kit/'config-homologacao.json')
    report['signed_catalogs']=[authenticate((kit/f'edicoes/novidades-v{i}.json').read_bytes(),
        (kit/f'edicoes/novidades-v{i}.json.sig').read_bytes(),config).sequence for i in (1,2)]
    result=subprocess.run(['openssl','verify','-x509_strict','-verify_hostname','homologacao.mainuan.test',
        '-CAfile',str(kit/'tls/ca-teste.crt'),str(kit/'tls/servidor.crt')],capture_output=True,text=True,check=True)
    report['tls_chain']=result.stdout.strip()
    report['data_only_packages']=[]
    for deb in sorted(kit.glob('repo-v*/pool/*.deb')):
        control=subprocess.run(['dpkg-deb','--ctrl-tarfile',str(deb)],capture_output=True,check=True).stdout
        payload=subprocess.run(['dpkg-deb','--fsys-tarfile',str(deb)],capture_output=True,check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(control)) as archive:
            assert not any(Path(p.name).name in ('preinst','postinst','prerm','postrm') for p in archive)
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
            regular=[p for p in archive if p.isfile()]
            assert len(regular)==1 and regular[0].name.startswith('./usr/share/mainuan-homologacao/')
            assert regular[0].mode & 0o111 == 0
        report['data_only_packages'].append(deb.name)
    with tempfile.TemporaryDirectory(prefix='mainuan-apt-leitura-') as tmp:
        root=Path(tmp)
        (root/'lists/partial').mkdir(parents=True)
        (root/'archives/partial').mkdir(parents=True)
        (root/'log').mkdir()
        (root/'tmp').mkdir()
        (root/'conf.d').mkdir()
        (root/'status').write_text('')
        (root/'sources.list').write_text(f'deb [signed-by={kit}/repo-chave-teste.asc] file:{kit}/repo-v1 ./\n')
        settings={'Dir::Etc::main':'-', 'Dir::Etc::parts':str(root/'conf.d'), 'Dir::Etc::sourcelist':str(root/'sources.list'),
                  'Dir::Etc::sourceparts':'-', 'Dir::State::status':str(root/'status'),
                  'Dir::State::lists':str(root/'lists'),'Dir::State::extended_states':str(root/'extended_states'),
                  'Dir::Cache::archives':str(root/'archives'),'Dir::Cache::pkgcache':str(root/'pkgcache.bin'),
                  'Dir::Cache::srcpkgcache':str(root/'srcpkgcache.bin'),'Dir::Log':str(root/'log')}
        apt_config=root/'apt.conf'
        apt_config.write_text(''.join(f'{key} "{value}";\n' for key,value in settings.items()))
        env=os.environ.copy();env['APT_CONFIG']=str(apt_config);env['TMPDIR']=str(root/'tmp');env['LC_ALL']='C'
        sandbox=['bwrap','--unshare-user','--unshare-net','--ro-bind','/','/','--bind',str(root),str(root),'--proc','/proc','--dev','/dev']
        update=subprocess.run(sandbox+['apt-get','update'],env=env,capture_output=True,text=True,timeout=30)
        report['apt_index_update_code']=update.returncode
        report['apt_index_output']=update.stdout+update.stderr
        if update.returncode:
            raise RuntimeError(report['apt_index_output'])
        names=json.loads((kit/'kit.json').read_text())['packages']
        if set(names) != {'mainuan-homologacao-alpha','mainuan-homologacao-beta','mainuan-homologacao-gamma'}:
            raise ValueError('Lista de pacotes fora do kit descartável esperado.')
        planned=subprocess.run(sandbox+['apt-get','--simulate','--no-remove','install','--',*names],env=env,capture_output=True,text=True,timeout=15)
        report['apt_solver_code']=planned.returncode
        report['apt_solver_output']=planned.stdout+planned.stderr
        if planned.returncode:
            raise RuntimeError(report['apt_solver_output'])
        # Consulta o cache Python dentro da mesma configuração isolada.
        probe='''import apt,json,sys
from pathlib import Path
sys.path.insert(0,SRC)
from mainuan_recursos.catalog import Config,authenticate
from mainuan_recursos.packages import build_plan
kit=Path(KIT)
catalog=authenticate((kit/'edicoes/novidades-v1.json').read_bytes(),(kit/'edicoes/novidades-v1.json.sig').read_bytes(),Config.load(kit/'config-homologacao.json'))
cache=apt.Cache()
plan=build_plan(catalog.releases[0],cache)
assert not plan.blockers and len(plan.pending)==3 and all(row.sha256 for row in plan.rows)
print(json.dumps({name:{'version':cache[name].candidate.version,'trusted':any(o.trusted for o in cache[name].candidate.origins),'installed':cache[name].is_installed,'sha256':cache[name].candidate.sha256} for name in NAMES}))
'''.replace('NAMES',repr(names)).replace('SRC',repr(str(Path(__file__).resolve().parents[1]/'src'))).replace('KIT',repr(str(kit)))
        observed=subprocess.run(sandbox+['/usr/bin/python3','-c',probe],env=env,capture_output=True,text=True,check=True,timeout=15)
        report['apt_candidates']=json.loads(observed.stdout)
        assert all(p['trusted'] and not p['installed'] and p['version']=='1.0' for p in report['apt_candidates'].values())
        # Conflito real em locks exclusivamente da raiz descartável. --download-only
        # nunca entrega pacotes ao dpkg, mesmo se o teste de bloqueio falhar.
        status_before=(root/'status').read_bytes()
        with ExitStack() as stack:
            for lock_path in (root/'lock-frontend',root/'lock',root/'archives/lock'):
                handle=stack.enter_context(lock_path.open('a+'))
                fcntl.lockf(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            blocked=subprocess.run(sandbox+['apt-get','-o','DPkg::Lock::Timeout=0','--download-only','--assume-yes','install','--',*names],
                                   env=env,capture_output=True,text=True,timeout=15)
            report['isolated_lock_conflict']={'code':blocked.returncode,'output':blocked.stdout+blocked.stderr,
                'holder_identified':str(os.getpid()) in blocked.stderr,
                'status_unchanged':(root/'status').read_bytes()==status_before}
            assert blocked.returncode != 0 and report['isolated_lock_conflict']['holder_identified']
            assert report['isolated_lock_conflict']['status_unchanged']

    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if not k.endswith('_output')},ensure_ascii=False))


if __name__=='__main__':
    main()
