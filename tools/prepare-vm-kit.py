#!/usr/bin/python3
"""Gera dados descartáveis de homologação; não configura APT nem instala pacotes."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from mainuan_recursos.catalog import Config, authenticate

HOST = 'homologacao.mainuan.test'
PACKAGES = ('mainuan-homologacao-alpha', 'mainuan-homologacao-beta', 'mainuan-homologacao-gamma')


def write_private(path, data):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:
        stream.write(data)


def run(args, **kwargs):
    return subprocess.run(args,check=True,capture_output=True,**kwargs)


def write_tls_server(target, now):
    # Certificado e chave apenas do servidor local de teste. Não há confiança de produção.
    tls=target/'tls';tls.mkdir(mode=0o700)
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Mainuan HOMOLOGACAO DESCARTAVEL')])
    ca=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(private.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(private.public_key()),critical=False)
        .add_extension(x509.KeyUsage(True,False,False,False,False,True,True,None,None),critical=True)
        .sign(private,hashes.SHA256()))
    server_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    server=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,HOST)]))
            .issuer_name(subject).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=2))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(HOST)]),critical=False)
            .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()),critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(private.public_key()),critical=False)
            .add_extension(x509.KeyUsage(True,False,True,False,False,False,False,None,None),critical=True)
            .sign(private,hashes.SHA256()))
    (tls/'ca-teste.crt').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (tls/'servidor.crt').write_bytes(server.public_bytes(serialization.Encoding.PEM))
    write_private(tls/'servidor.key',server_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    # A chave privada de assinatura do catálogo e a CA são descartadas; edições já assinadas bastam.
    server_script='''#!/usr/bin/python3
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import ssl
root=Path(__file__).resolve().parent
handler=partial(SimpleHTTPRequestHandler,directory=str(root/'site'))
server=ThreadingHTTPServer(('127.0.0.1',443),handler)
context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(root/'tls/servidor.crt',root/'tls/servidor.key')
server.socket=context.wrap_socket(server.socket,server_side=True)
server.serve_forever()
'''
    (target/'servir-catalogo.py').write_text(server_script)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='diretório novo, fora da configuração de produção')
    opts=parser.parse_args()
    target=opts.output.resolve()
    target.mkdir(mode=0o700,parents=True,exist_ok=False)
    now=datetime.now(timezone.utc).replace(microsecond=0)
    with tempfile.TemporaryDirectory(prefix='mainuan-chave-teste-') as temp:
        scratch=Path(temp)
        gpg_home=scratch/'gnupg';gpg_home.mkdir(mode=0o700)
        gpg=['gpg','--homedir',str(gpg_home),'--batch','--pinentry-mode','loopback','--passphrase','']
        try:
            run(gpg+['--quick-generate-key','Mainuan TESTE DESCARTAVEL <teste@example.invalid>','ed25519','sign','2d'])
            public=run(gpg+['--armor','--export']).stdout
            (target/'repo-chave-teste.asc').write_bytes(public)
            fingerprint=next(line.split(':')[9] for line in run(gpg+['--with-colons','--list-keys'],text=True).stdout.splitlines() if line.startswith('fpr:'))
            for stage in (1,2):
                repo=target/f'repo-v{stage}';repo.mkdir()
                pool=repo/'pool';pool.mkdir()
                for name in PACKAGES:
                    package_root=scratch/f'{name}-{stage}'
                    control=package_root/'DEBIAN/control';control.parent.mkdir(parents=True)
                    control.write_text(f'Package: {name}\nVersion: {stage}.0\nArchitecture: all\nSection: misc\nPriority: optional\nMaintainer: Mainuan Homologacao <teste@example.invalid>\nDescription: Dados descartaveis de homologacao\n Somente um arquivo de texto; sem executaveis, dependencias ou scripts.\n')
                    payload=package_root/f'usr/share/mainuan-homologacao/{name}/info.txt'
                    payload.parent.mkdir(parents=True)
                    payload.write_text(f'HOMOLOGACAO DESCARTAVEL — {name} {stage}.0\n')
                    run(['dpkg-deb','--build','--root-owner-group',str(package_root),str(pool/f'{name}_{stage}.0_all.deb')])
                packages=run(['dpkg-scanpackages','pool','/dev/null'],cwd=repo).stdout
                (repo/'Packages').write_bytes(packages)
                (repo/'Packages.gz').write_bytes(gzip.compress(packages,mtime=0))
                release=('Origin: Mainuan-Homologacao-Descartavel\nLabel: Somente testes em VM\n'
                         f'Date: {format_datetime(now,usegmt=True)}\nValid-Until: {format_datetime(now+timedelta(days=2),usegmt=True)}\n'
                         'Architectures: amd64 arm64 all\nDescription: Repositorio descartavel sem programas executaveis\nSHA256:\n')
                for name in ('Packages','Packages.gz'):
                    data=(repo/name).read_bytes()
                    release+=f' {hashlib.sha256(data).hexdigest()} {len(data)} {name}\n'
                (repo/'Release').write_text(release)
                run(gpg+['--yes','--clearsign','--output',str(repo/'InRelease'),str(repo/'Release')])
                run(gpg+['--yes','--detach-sign','--output',str(repo/'Release.gpg'),str(repo/'Release')])
        finally:
            subprocess.run(['gpgconf','--homedir',str(gpg_home),'--kill','all'],capture_output=True)
    key=ed25519.Ed25519PrivateKey.generate()
    public=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    config={'manifest_url':f'https://{HOST}/catalog/novidades.json','official_hosts':[HOST,'github.com'],
            'manifest_prefixes':[f'https://{HOST}/catalog/'],'article_prefixes':['https://github.com/mainuan/'],
            'keys':{'descartavel-vm':public}}
    config_path=target/'config-homologacao.json';config_path.write_text(json.dumps(config,indent=2))
    editions=target/'edicoes';editions.mkdir()
    for stage in (1,2):
        obj={'schema_version':1,'sequence':stage,'published_at':now.isoformat(),
             'expires_at':(now+timedelta(days=2)).isoformat(),'releases':[
             {'id':'mainuan-homologacao','version':str(stage),'title':f'Homologação descartável {stage}',
              'summary':'Três pacotes de teste contendo somente arquivos de texto. Instalar apenas na VM com snapshot.',
              'article_url':'https://github.com/mainuan/atualizadorderecursos',
              'features':[{'title':f'Dados de teste {name.rsplit("-",1)[1]}',
                           'packages':[{'name':name,'min_version':f'{stage}.0', 'architecture':'all',
                                        'sha256':hashlib.sha256((target/f'repo-v{stage}/pool/{name}_{stage}.0_all.deb').read_bytes()).hexdigest()}]}
                          for name in PACKAGES]}]}
        raw=json.dumps(obj,ensure_ascii=False,indent=2).encode()
        signature=json.dumps({'key_id':'descartavel-vm','signature':base64.b64encode(key.sign(raw)).decode()}).encode()
        authenticate(raw,signature,Config.load(config_path))
        (editions/f'novidades-v{stage}.json').write_bytes(raw)
        (editions/f'novidades-v{stage}.json.sig').write_bytes(signature)
    site=target/'site/catalog';site.mkdir(parents=True)
    (site/'novidades.json').write_bytes((editions/'novidades-v1.json').read_bytes())
    (site/'novidades.json.sig').write_bytes((editions/'novidades-v1.json.sig').read_bytes())
    write_tls_server(target, now)
    report={'test_only':True,'created_at':now.isoformat(),'expires_at':(now+timedelta(days=2)).isoformat(),
            'apt_key_fingerprint':fingerprint,'packages':list(PACKAGES),
            'production_modified':False,'private_signing_keys_discarded':True,
            'note':'Não instala ou configura o host. Consulte docs/vm-final.md e prepare snapshot na VM.'}
    (target/'kit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':
    main()
