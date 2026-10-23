#!/usr/bin/python3
"""Demonstra a publicação dos dois .txt, com três repositórios/DEBs fictícios."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from publication import encoded, publish
from publication_fixture import Fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='diretório novo; nunca configuração de produção')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='mainuan-publicacao-ficticia-') as temp:
        fixture = Fixture(Path(temp))
        try:
            packages = '\n'.join(fixture.programs).encode() + b'\n'
            message = 'Olá! O Mainuan tem novidades. Confira quais são:\n\nUma publicação inteiramente fictícia.'.encode()
            (args.output / 'packages.txt').write_bytes(packages)
            (args.output / 'message.txt').write_bytes(message)
            # Chaves privadas só no temporário/memória; descartadas após gerar duas edições.
            previous = Path(temp) / 'vazio'
            previous.mkdir()
            for stage in (1, 2):
                output = args.output / f'edicao-{stage}'
                result = publish(packages + (b'# nova aprovacao\n' if stage == 2 else b''), message,
                                 policy=fixture.policy, github=fixture.github(stage), previous_root=previous,
                                 output=output, private_key=fixture.private, gpg_home=fixture.gpg_home,
                                 approval_commit=str(stage) * 40, approval_time=fixture.now, now=fixture.now,
                                 production=False)
                previous = output
            (args.output / 'apt-chave-teste.gpg').write_bytes(__import__('subprocess').check_output([
                'gpg', '--homedir', str(fixture.gpg_home), '--batch', '--export', fixture.policy['apt_fingerprint']]))
            config = {'manifest_url': 'https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/catalogo/novidades.json',
                      'official_hosts': ['raw.githubusercontent.com', 'github.com'],
                      'manifest_prefixes': ['https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/catalogo/'],
                      'article_prefixes': ['https://github.com/mainuan/'],
                      'keys': {fixture.policy['catalog_key_id']: fixture.policy['catalog_public_key']}}
            (args.output / 'config-teste.json').write_bytes(encoded(config))
            report = {'test_only': True, 'programas': len(result['selected']), 'edicoes': 2,
                      'assinaturas_verificadas': True, 'instalacao_real': False, 'producao_alterada': False,
                      'apt_fingerprint_teste': fixture.policy['apt_fingerprint']}
            (args.output / 'resultado.json').write_bytes(encoded(report))
            print(json.dumps(report, ensure_ascii=False))
        finally:
            fixture.close()


if __name__ == '__main__':
    main()
