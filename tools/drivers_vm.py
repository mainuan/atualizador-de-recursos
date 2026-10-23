#!/usr/bin/python3
"""Operações restritas à VM do kit descartável Gestão de Drivers 1.0."""
import argparse
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import hashlib
import fcntl
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile

NAME = 'mainuan-gestao-drivers'
DEB = NAME + '_1.0_all.deb'
SHA = 'd7a1c98743a204f6b5770c7746cb02b3b4d66c09d2d368966118ac39fa47b912'
SCRIPT_SHA = '2327e9c32a172d42b86b86b63b6f74abe72d7cfe34e3bcbcb5b1942c839c2b7b'
HOST = 'homologacao.mainuan.test'
ORIGIN = 'Mainuan-Homologacao-Gestao-Drivers'
ROOT = Path('/opt/mainuan-homologacao-drivers')
CONFIG = Path('/etc/mainuan/atualizador-recursos.json')
SOURCE = Path('/etc/apt/sources.list.d/mainuan-homologacao-drivers.list')
KEY = Path('/etc/apt/keyrings/mainuan-homologacao-drivers.gpg')
PREF = Path('/etc/apt/preferences.d/99-mainuan-homologacao-drivers')
UNIT = 'mainuan-homologacao-drivers.service'
POLICY = f'''Package: {NAME}
Pin: release o={ORIGIN}
Pin-Priority: 1001

Package: *
Pin: release *
Pin-Priority: -1
'''


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def run(args, **kwargs):
    result = subprocess.run(args, check=True, capture_output=True, text=True, **kwargs)
    return result.stdout


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def audit_deb(deb):
    """Inspeciona bytes; nunca extrai scripts para execução nem instala o .deb."""
    require(digest(deb) == SHA, 'SHA-256 diferente do artefato oficial aprovado.')
    control = run(['dpkg-deb', '--field', str(deb)])
    for field, expected in [('Package', NAME), ('Version', '1.0'), ('Architecture', 'all')]:
        require(f'{field}: {expected}' in control.splitlines(), 'Controle Debian divergente: ' + field)
    data = subprocess.check_output(['dpkg-deb', '--ctrl-tarfile', str(deb)])
    scripts = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            require(name in ('', '.', 'control', 'md5sums', 'preinst', 'postinst', 'prerm', 'postrm'),
                    'Controle adicional não auditado: ' + name)
            if name in ('preinst', 'postinst', 'prerm', 'postrm'):
                raw = archive.extractfile(member).read()
                require(hashlib.sha256(raw).hexdigest() == SCRIPT_SHA, 'Script de manutenção divergente.')
                scripts[name] = raw.decode()
    require(len(scripts) == 4, 'Conjunto de scripts de manutenção divergente.')
    data = subprocess.check_output(['dpkg-deb', '--fsys-tarfile', str(deb)])
    payload = []
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            path = member.name.removeprefix('./').rstrip('/')
            require(not path.startswith('/') and '..' not in Path(path).parts, 'Caminho inseguro no pacote.')
            if not member.isdir():
                require(path.startswith(('usr/lib/mainuan/', 'usr/share/doc/', 'usr/share/icons/',
                                         'usr/share/locale/', 'usr/share/applications/',
                                         'usr/share/mainuan/mainuan-gestao-drivers/', 'usr/share/man/'))
                        or path == 'usr/bin/' + NAME, 'Arquivo fora das áreas aprovadas: ' + path)
                require(member.isfile() or member.issym(), 'Tipo especial no pacote: ' + path)
                if member.issym():
                    target = member.linkname
                    require(path == 'usr/bin/' + NAME and target in (
                        '/usr/lib/mainuan/mainuan-gestao-drivers/mainuan-gestao-drivers',
                        '../lib/mainuan/mainuan-gestao-drivers/mainuan-gestao-drivers'),
                        'Link não aprovado: ' + path + ' -> ' + target)
                payload.append({'path': path, 'link': member.linkname if member.issym() else ''})
    return {'control': control, 'scripts': scripts, 'payload': payload, 'sha256': SHA,
            'note': 'Sem módulos, firmware, DKMS, serviços ou autostart. Não executar o gestor neste ensaio.'}


def installed_modules():
    sys.path.insert(0, '/usr/lib/mainuan-atualizador-recursos')
    from mainuan_recursos.catalog import Config, authenticate
    return Config, authenticate


def verify_kit(kit):
    metadata = json.loads((kit / 'kit.json').read_text())
    require(metadata['test_only'] is True and metadata['package_sha256'] == SHA, 'Kit não aprovado para este ensaio.')
    require(datetime.now(timezone.utc) < datetime.fromisoformat(metadata['expires_at']),
            'Kit expirado. Gere outro kit; não desative a validação de validade.')
    # Verifica inclusive scripts transferidos. O SHA externo do .tar.gz deve ser comparado antes de extrair.
    for line in (kit / 'ARQUIVOS.sha256').read_text().splitlines():
        expected, relative = line.split('  ', 1)
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'Checksum com caminho inválido.')
        require(digest(kit / relative) == expected, 'Arquivo alterado: ' + relative)
    Config, authenticate = installed_modules()
    catalog = authenticate((kit / 'site/catalog/novidades.json').read_bytes(),
                           (kit / 'site/catalog/novidades.json.sig').read_bytes(),
                           Config.load(kit / 'config-homologacao.json'))
    require(len(catalog.releases) == 1 and len(catalog.releases[0].packages) == 1, 'Catálogo fora do escopo.')
    package = catalog.releases[0].packages[0]
    require((package.name, package.min_version, package.architecture, package.sha256) ==
            (NAME, '1.0', 'all', SHA), 'Pacote do catálogo divergente.')
    run(['gpgv', '--keyring', str(kit / 'repo-chave-teste.gpg'), str(kit / 'apt/InRelease')])
    run(['gpgv', '--keyring', str(kit / 'repo-chave-teste.gpg'),
         str(kit / 'apt/Release.gpg'), str(kit / 'apt/Release')])
    audit_deb(kit / 'apt/pool' / DEB)
    return metadata, catalog.releases[0]


def vm_only(root=False):
    try:
        virtual = run(['systemd-detect-virt', '--vm']).strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError('Operação permitida somente em máquina virtual. Nenhuma configuração foi alterada.') from exc
    require(bool(virtual), 'Operação permitida somente em máquina virtual.')
    require((os.geteuid() == 0) == root, 'Use sudo para configurar/restaurar; use seu usuário comum para plano/interface.')
    installed_modules()
    from mainuan_recursos.session import SessionKind, session_kind, system_identity
    require(session_kind() == SessionKind.INSTALLED, 'A VM precisa estar instalada; sessão Live/desconhecida bloqueada.')
    system = system_identity()
    require(system['distro_id'] in ('mainuan', 'ubuntu') and system['version_id'] in ('2026', '26.04'),
            'Kit destinado ao Mainuan/Kubuntu 26.04. Identificação observada: ' + str(system))


@contextmanager
def apt_guard():
    """Locks padrão somente durante preparação/limpeza; nunca remove ou contorna locks."""
    with ExitStack() as stack:
        for name in ('/var/lib/dpkg/lock-frontend', '/var/lib/dpkg/lock', '/var/cache/apt/archives/lock'):
            path = Path(name)
            require(path.is_file(), 'Lock APT/dpkg esperado ausente: ' + name)
            stream = stack.enter_context(path.open('r+'))
            try:
                fcntl.lockf(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('APT/Discover está ocupado. Aguarde; nenhum bloqueio será contornado.') from exc
        yield


def package_state():
    lines = run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${Status}\n']).splitlines()
    return {p[0]: p[1:] for line in lines if len(p := line.split('\t')) == 3 and p[2].endswith(' ok installed')}


def hardware_state():
    """Somente leitura; hashes em fluxo, sem carregar firmware inteiro na memória."""
    result = {}
    paths = ('/etc/modprobe.d', '/etc/modules-load.d', '/etc/modules', '/etc/default/grub',
             '/etc/initramfs-tools', '/boot', '/usr/lib/modules', '/usr/lib/firmware', '/usr/src', '/var/lib/dkms')
    for base in paths:
        root = Path(base)
        files = sorted(root.rglob('*')) if root.is_dir() else [root]
        for path in files:
            if path.is_symlink():
                result[str(path)] = 'link:' + os.readlink(path)
            elif path.is_file():
                result[str(path)] = digest(path)
    result['/proc/modules:names'] = sorted(line.split()[0] for line in Path('/proc/modules').read_text().splitlines())
    return result


def state_dir(metadata):
    # Isola sequência anti-retrocesso, histórico e adiamento da instalação normal.
    return Path.home() / '.local/state' / ('mainuan-homologacao-drivers-' + metadata['id'])


def test_environment(directory=None):
    env = dict(os.environ, SSL_CERT_FILE=str(ROOT / 'tls/ca-teste.crt'))
    if directory is not None:
        env['XDG_STATE_HOME'] = str(directory)
    for key in ('NO_PROXY', 'no_proxy'):
        env[key] = ','.join(filter(None, [env.get(key), HOST, '127.0.0.1']))
    return env


def active():
    metadata, release = verify_kit(ROOT)
    require(CONFIG.read_bytes() == (ROOT / 'config-homologacao.json').read_bytes(), 'Configuração experimental não está ativa.')
    require(PREF.read_text() == POLICY, 'Política de contenção APT foi alterada.')
    require(not Path('/etc/apt/preferences').exists(), 'Surgiu outra política APT; interrompa o teste.')
    require(list(PREF.parent.iterdir()) == [PREF], 'Surgiu outra política APT; interrompa o teste.')
    require(SOURCE.read_text() == f'deb [signed-by={KEY}] file:{ROOT}/apt ./\n', 'Fonte APT de teste alterada.')
    require(KEY.read_bytes() == (ROOT / 'repo-chave-teste.gpg').read_bytes(), 'Chave APT de teste alterada.')
    return metadata, release


def cleanup():
    backup = ROOT / 'backup'
    require(backup.is_dir(), 'Backup da configuração não encontrado. Restaure o snapshot.')
    journal = json.loads((backup / 'journal.json').read_text())
    # Valida TODOS os conflitos antes de restaurar, preservando o backup em caso de dúvida.
    for filename, expected in journal['written'].items():
        path = Path(filename)
        require(not path.exists() or digest(path) == expected, 'Arquivo modificado durante o teste: ' + filename + '. Restaure o snapshot.')
    if journal.get('preferences_file_moved'):
        require(not Path('/etc/apt/preferences').exists(), 'Política APT criada durante o teste; restaure o snapshot.')
    if journal.get('preferences_ready'):
        require(not PREF.parent.exists() or all(p == PREF for p in PREF.parent.iterdir()), 'Políticas APT alteradas; restaure o snapshot.')
    subprocess.run(['systemctl', 'stop', UNIT], capture_output=True)
    subprocess.run(['systemctl', 'reset-failed', UNIT], capture_output=True)
    for filename in journal['written']:
        path = Path(filename)
        if filename in journal['backed_up']:
            shutil.copy2(backup / journal['backed_up'][filename], path)
        else:
            path.unlink(missing_ok=True)
    if journal.get('preferences_ready'):
        if PREF.parent.exists() and journal.get('preferences_dir_moved'):
            PREF.parent.rmdir()
    if journal.get('preferences_dir_moved') and (backup / 'preferences.d').exists():
        shutil.move(str(backup / 'preferences.d'), str(PREF.parent))
    if journal.get('preferences_file_moved') and (backup / 'preferences').exists():
        shutil.move(backup / 'preferences', Path('/etc/apt/preferences'))
    # Apenas os índices deste caminho file:, nunca os índices das fontes normais.
    for path in Path('/var/lib/apt/lists').glob('*mainuan-homologacao-drivers_apt_*'):
        if path.is_file():
            path.unlink()
    (backup / 'RESTAURADO').write_text(datetime.now(timezone.utc).isoformat())
    print('Configuração original restaurada; produção continua desativada. O aplicativo instalado NÃO foi removido.')
    print('Para desfazer a instalação do gestor, restaure o snapshot. Arquivos/evidências do kit permanecem em ' + str(ROOT))


def prepare(kit, snapshot):
    require(snapshot.strip(), 'Informe o nome do snapshot previamente criado e testado no Boxes.')
    verify_kit(kit)
    require(not ROOT.exists(), f'{ROOT} já existe; não sobrescreverei um ensaio anterior. Restaure o snapshot.')
    require(CONFIG.is_file() and not CONFIG.is_symlink(), 'Configuração original ausente ou simbólica.')
    require(json.loads(CONFIG.read_text()).get('keys') == {}, 'Produção já tem chaves; não substituir automaticamente.')
    require(not SOURCE.exists() and not KEY.exists(), 'Fonte/chave experimental já existe.')
    require(NAME not in package_state(), 'O gestor já está instalado. Use o snapshot anterior à instalação.')
    require(not run(['dpkg', '--audit']).strip(), 'Há pacotes com configuração incompleta. Resolva na VM antes do snapshot.')
    require(not Path('/etc/sudoers.d/mainuan-gestao-drivers-gtk-legacy').exists(), 'Regra sudoers legada presente: use VM limpa.')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 443))  # Falha antes de modificar configurações se a porta estiver ocupada.
    shutil.copytree(kit, ROOT)
    for path in [ROOT, *ROOT.rglob('*')]:
        os.chown(path, 0, 0)
        path.chmod(0o755 if path.is_dir() else 0o644)
    (ROOT / 'tls/servidor.key').chmod(0o600)
    backup = ROOT / 'backup'; backup.mkdir(mode=0o700)
    print('Registrando pacotes e arquivos de hardware (somente leitura; pode levar alguns minutos)…', flush=True)
    dump(backup / 'pacotes-antes.json', package_state())
    dump(backup / 'hardware-antes.json', hardware_state())
    journal = {'snapshot_informado': snapshot, 'written': {}, 'backed_up': {}}

    def checkpoint():
        dump(backup / 'journal.json', journal)

    def write(path, data):
        # Registra antes da mutação, permitindo restaurar mesmo se houver falha parcial.
        if path.exists():
            name = 'original-' + str(len(journal['backed_up']))
            shutil.copy2(path, backup / name)
            journal['backed_up'][str(path)] = name
        journal['written'][str(path)] = hashlib.sha256(data).hexdigest()
        checkpoint()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o644)

    checkpoint()
    try:
        # Suspende preferências anteriores sem perder seus bytes, nomes ou permissões.
        for path in (Path('/etc/apt/preferences'), PREF.parent):
            require(not path.is_symlink(), 'Preferências APT simbólicas não suportadas neste ensaio.')
        if Path('/etc/apt/preferences').exists():
            shutil.move(Path('/etc/apt/preferences'), backup / 'preferences')
            journal['preferences_file_moved'] = True; checkpoint()
        if PREF.parent.exists():
            shutil.move(str(PREF.parent), backup / 'preferences.d')
            journal['preferences_dir_moved'] = True; checkpoint()
        journal['preferences_ready'] = True; checkpoint()
        write(PREF, POLICY.encode())
        write(KEY, (ROOT / 'repo-chave-teste.gpg').read_bytes())
        write(SOURCE, f'deb [signed-by={KEY}] file:{ROOT}/apt ./\n'.encode())
        print(run(['apt-get', '-o', f'Dir::Etc::sourcelist={SOURCE}', '-o', 'Dir::Etc::sourceparts=-',
                   '-o', 'APT::Get::List-Cleanup=false', '-o', 'APT::Update::Error-Mode=any', 'update']))
        # --simulate apenas. Não contorna locks nem executa dpkg.
        output = run(['apt-get', '--simulate', '--no-remove', 'install', NAME + '=1.0'], env={**os.environ, 'LC_ALL': 'C'})
        print(output)
        changes = [line.split()[1] for line in output.splitlines() if line.startswith(('Inst ', 'Remv '))]
        require(changes == [NAME], 'O APT propôs alterações além do gestor. Nada foi instalado; preparação será restaurada.')
        from mainuan_recursos.packages import build_plan
        _, release = verify_kit(ROOT)
        plan = build_plan(release)
        require(not plan.blockers and len(plan.pending) == 1, 'O catálogo não corresponde ao candidato APT confiável.')
        hosts = Path('/etc/hosts')
        require(HOST not in hosts.read_text(), 'Hostname de homologação já está configurado.')
        write(hosts, hosts.read_bytes() + f'\n127.0.0.1 {HOST} # mainuan-homologacao-drivers\n'.encode())
        write(CONFIG, (ROOT / 'config-homologacao.json').read_bytes())
        run(['systemd-run', '--unit=' + UNIT, '--property=NoNewPrivileges=yes',
             '--property=ProtectSystem=strict', '--property=PrivateTmp=yes',
             '/usr/bin/python3', str(ROOT / 'servir-catalogo.py')])
        print('Preparação concluída SEM instalar pacotes. Execute plano com seu usuário comum.')
    except BaseException:
        cleanup()
        raise


def probe():
    metadata, release = active()
    # Exercita também HTTPS e autenticação pelo mesmo código utilizado no aplicativo.
    os.environ.update(test_environment())
    from mainuan_recursos.catalog import Config, authenticate, fetch
    raw, signature = fetch(Config.load())
    catalog = authenticate(raw, signature, Config.load())
    require(catalog.releases == (release,), 'Servidor apresentou uma edição diferente do kit aprovado.')
    from PyQt6.QtCore import QCoreApplication
    from mainuan_recursos.controller import Controller
    from mainuan_recursos.packages import identity
    app = QCoreApplication([])
    controller = Controller()
    result = {'ok': False}

    def save_plan(evidence):
        directory = state_dir(metadata); directory.mkdir(parents=True, exist_ok=True)
        dump(directory / 'plano.json', {'dpkg_status': digest('/var/lib/dpkg/status'),
                                       'effects': evidence, 'kit': metadata['id']})

    def prepared(value):
        try:
            require(len(value.evidence) == 1 and identity(value.evidence[0][1]) == (NAME, '1.0', 'all'),
                    'O PackageKit propôs outras alterações. NÃO instalar.')
            require(value.evidence[0][0] == 12 and not value.evidence[0][2], 'O efeito precisa ser uma única instalação nova.')
            save_plan(value.evidence)
            print('PackageKit: instalar somente Gestão de Drivers 1.0 (all). Nenhuma dependência será alterada.')
            print('Simulação concluída. Nenhuma autorização de instalação foi solicitada.')
            result['ok'] = True
        except Exception as exc:
            print(str(exc), file=sys.stderr)
        controller.cancel_preparation()  # Deliberadamente NÃO chama confirm().
        app.quit()

    def completed(success, message, plan):
        print(message, file=sys.stderr)
        if success and plan and plan.complete:
            save_plan(())
            result['ok'] = True
            print('Recurso já recebido. A interface pode ser aberta para conferir; nenhuma reinstalação é necessária.')
        app.quit()

    controller.prepared.connect(prepared)
    controller.completed.connect(completed)
    controller.progress.connect(lambda text, percent: print(text, flush=True))
    controller.prepare(release)
    app.exec()
    require(result['ok'], 'Plano não aprovado. Não abra a instalação; guarde a mensagem e restaure o ambiente se necessário.')


def launch():
    metadata, _ = active()
    directory = state_dir(metadata)
    approved = json.loads((directory / 'plano.json').read_text())
    require(approved['kit'] == metadata['id'] and approved['dpkg_status'] == digest('/var/lib/dpkg/status'),
            'Estado de pacotes mudou. Execute plano novamente.')
    env = test_environment(directory)
    os.execve('/usr/bin/mainuan-atualizador-recursos', ['mainuan-atualizador-recursos'], env)


def verify_result():
    print('Conferindo pacotes e arquivos de hardware, sem executar o gestor…', flush=True)
    before = json.loads((ROOT / 'backup/pacotes-antes.json').read_text())
    after = package_state()
    differences = {name: {'antes': before.get(name), 'depois': after.get(name)}
                   for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    require(differences == {NAME: {'antes': None, 'depois': ['1.0', 'install ok installed']}},
            'Resultado difere de uma única instalação: ' + json.dumps(differences, ensure_ascii=False))
    old = json.loads((ROOT / 'backup/hardware-antes.json').read_text())
    new = hardware_state()
    changed = [key for key in old.keys() | new.keys() if old.get(key) != new.get(key)]
    dump(ROOT / 'resultado.json', {'package_changes': differences, 'hardware_differences': changed,
                                 'checked_at': datetime.now(timezone.utc).isoformat()})
    require(not changed, 'Arquivos/módulos de hardware mudaram: ' + ', '.join(changed) + '. Investigue e restaure snapshot.')
    print('CONFIRMADO: somente mainuan-gestao-drivers 1.0 foi instalado; arquivos e lista de módulos de hardware preservados.')
    print('O gestor NÃO foi executado. Confirme na interface do Atualizador: recurso já recebido, sem reinstalação.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acao', choices=('inspecionar', 'preparar', 'plano', 'abrir', 'verificar', 'limpar'))
    parser.add_argument('--snapshot-confirmado', default='')
    args = parser.parse_args()
    kit = Path(__file__).resolve().parent
    if args.acao == 'inspecionar':
        metadata, _ = verify_kit(kit)
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        print((kit / 'auditoria-pacote.json').read_text())
        return
    vm_only(root=args.acao in ('preparar', 'verificar', 'limpar'))
    if args.acao == 'preparar':
        with apt_guard():
            prepare(kit, args.snapshot_confirmado)
    elif args.acao == 'plano':
        probe()
    elif args.acao == 'abrir':
        launch()
    elif args.acao == 'verificar':
        verify_result()
    elif args.acao == 'limpar':
        with apt_guard():
            cleanup()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        detail = (exc.stdout or '') + (exc.stderr or '') if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print('INTERROMPIDO: ' + detail, file=sys.stderr)
        sys.exit(1)
