"""Barreiras do kit real; sem baixar pacotes nem alterar APT/dpkg do anfitrião."""
from datetime import datetime, timedelta, timezone
from contextlib import ExitStack
import hashlib
import io
import json
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import drivers_vm as vm


SCRIPT = b'''#!/bin/sh
set -e
# Automatically added by dh_installdeb/13.31ubuntu1
dpkg-maintscript-helper rm_conffile /etc/sudoers.d/mainuan-gestao-drivers-gtk-legacy 0.5\\~ mainuan-gestao-drivers -- "$@"
# End automatically added section
'''


def archive(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w') as stream:
        for name, value in entries:
            member = tarfile.TarInfo(name)
            if isinstance(value, tuple):
                member.type = tarfile.SYMTYPE; member.linkname = value[0]
                stream.addfile(member)
            else:
                member.size = len(value)
                stream.addfile(member, io.BytesIO(value))
    return out.getvalue()


class DriversKitTests(unittest.TestCase):
    def audited(self, extra_control=(), extra_payload=(), script=SCRIPT):
        control = [('control', b'control'), ('md5sums', b'checksums')]
        control += [(name, script) for name in ('preinst', 'postinst', 'prerm', 'postrm')]
        payload = [('usr/share/mainuan/mainuan-gestao-drivers/icons/mainuan.svg', b'icon'),
                   ('usr/bin/' + vm.NAME, ('../lib/mainuan/mainuan-gestao-drivers/mainuan-gestao-drivers',))]
        with patch.object(vm, 'digest', return_value=vm.SHA), patch.object(vm, 'run',
            return_value='Package: mainuan-gestao-drivers\nVersion: 1.0\nArchitecture: all\n'), \
            patch.object(vm.subprocess, 'check_output', side_effect=[archive(control + list(extra_control)), archive(payload + list(extra_payload))]):
            return vm.audit_deb(Path('/pacote-nao-executado.deb'))

    def test_expected_maintainer_script_hash_is_exact(self):
        self.assertEqual(hashlib.sha256(SCRIPT).hexdigest(), vm.SCRIPT_SHA)

    def test_approved_scripts_and_payload_are_accepted(self):
        result = self.audited()
        self.assertEqual(len(result['scripts']), 4)
        self.assertEqual(result['sha256'], vm.SHA)

    def test_tampered_deb_is_rejected_before_inspection(self):
        with patch.object(vm, 'digest', return_value='0' * 64), patch.object(vm, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
                vm.audit_deb(Path('/nao-lido'))
            run.assert_not_called()

    def test_changed_maintainer_script_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Script'):
            self.audited(script=SCRIPT + b'echo changed\n')

    def test_additional_control_trigger_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Controle adicional'):
            self.audited(extra_control=[('triggers', b'activate anything')])

    def test_driver_firmware_boot_and_autostart_payloads_are_rejected(self):
        for path in ('usr/lib/modules/test.ko', 'usr/lib/firmware/test.bin', 'boot/test',
                     'etc/xdg/autostart/test.desktop', 'usr/lib/systemd/system/test.service'):
            with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, 'áreas aprovadas'):
                self.audited(extra_payload=[(path, b'data')])

    def test_unsafe_paths_and_links_are_rejected(self):
        for path, value in [('usr/share/doc/../../etc/test', b'data'),
                            ('usr/share/doc/test', ('/etc/hosts',))]:
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                self.audited(extra_payload=[(path, value)])

    def test_expired_kit_is_rejected_before_loading_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vm.dump(root / 'kit.json', {'test_only': True, 'package_sha256': vm.SHA,
                'expires_at': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()})
            with patch.object(vm, 'installed_modules') as modules:
                with self.assertRaisesRegex(RuntimeError, 'expirado'):
                    vm.verify_kit(root)
                modules.assert_not_called()

    def test_physical_host_refused_before_any_mutation(self):
        with patch.object(vm, 'run', return_value=''), patch.object(vm, 'installed_modules') as modules:
            with self.assertRaisesRegex(RuntimeError, 'máquina virtual'):
                vm.vm_only(root=True)
            modules.assert_not_called()

    def test_interface_must_run_as_regular_user(self):
        with patch.object(vm, 'run', return_value='kvm\n'), patch.object(vm.os, 'geteuid', return_value=0):
            with self.assertRaisesRegex(RuntimeError, 'usuário comum'):
                vm.vm_only(root=False)

    def test_non_virtual_machine_exit_has_clear_refusal(self):
        with patch.object(vm, 'run', side_effect=subprocess.CalledProcessError(1, ['systemd-detect-virt'])):
            with self.assertRaisesRegex(RuntimeError, 'Nenhuma configuração'):
                vm.vm_only(root=True)

    def test_existing_package_manager_lock_is_not_bypassed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'lock'; path.touch()
            with patch.object(vm, 'Path', return_value=path), \
                patch.object(vm.fcntl, 'lockf', side_effect=BlockingIOError):
                with self.assertRaisesRegex(RuntimeError, 'nenhum bloqueio será contornado'):
                    with vm.apt_guard():
                        self.fail('A operação não poderia obter o lock.')

    def test_state_and_trust_are_scoped_to_test_process(self):
        with patch.object(vm.os, 'environ', {'NO_PROXY': 'example.invalid'}):
            env = vm.test_environment(Path('/tmp/test-state'))
        self.assertEqual(env['SSL_CERT_FILE'], str(vm.ROOT / 'tls/ca-teste.crt'))
        self.assertEqual(env['XDG_STATE_HOME'], '/tmp/test-state')
        self.assertIn(vm.HOST, env['NO_PROXY'])
        self.assertNotIn('--demo', json.dumps(env))

    def test_changed_dpkg_state_prevents_launch(self):
        metadata = {'id': 'test'}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            vm.dump(directory / 'plano.json', {'kit': 'test', 'dpkg_status': 'old'})
            with patch.object(vm, 'active', return_value=(metadata, None)), \
                patch.object(vm, 'state_dir', return_value=directory), patch.object(vm, 'digest', return_value='new'), \
                patch.object(vm.os, 'execve') as execute:
                with self.assertRaisesRegex(RuntimeError, 'mudou'):
                    vm.launch()
                execute.assert_not_called()

    def test_launch_runs_installed_application_without_demo_or_sudo(self):
        metadata = {'id': 'test'}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            vm.dump(directory / 'plano.json', {'kit': 'test', 'dpkg_status': 'unchanged'})
            with patch.object(vm, 'active', return_value=(metadata, None)), \
                patch.object(vm, 'state_dir', return_value=directory), patch.object(vm, 'digest', return_value='unchanged'), \
                patch.object(vm.os, 'execve') as execute:
                vm.launch()
                binary, args, env = execute.call_args.args
                self.assertEqual(binary, '/usr/bin/mainuan-atualizador-recursos')
                self.assertEqual(args, ['mainuan-atualizador-recursos'])
                self.assertEqual(env['XDG_STATE_HOME'], str(directory))

    def test_any_additional_installed_package_fails_final_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'backup').mkdir()
            vm.dump(root / 'backup/pacotes-antes.json', {})
            with patch.object(vm, 'ROOT', root), patch.object(vm, 'package_state',
                return_value={vm.NAME: ['1.0', 'install ok installed'], 'nvidia-driver-test': ['1', 'install ok installed']}):
                with self.assertRaisesRegex(RuntimeError, 'única instalação'):
                    vm.verify_result()

    def test_inventory_includes_installed_packages_on_hold(self):
        with patch.object(vm, 'run', return_value='driver\t1.0\thold ok installed\nremoved\t1\tdeinstall ok config-files\n'):
            self.assertEqual(vm.package_state(), {'driver': ['1.0', 'hold ok installed']})

    def configuration_roundtrip(self, fail_solver=False):
        # Todos os caminhos absolutos e subprocessos mutáveis são substituídos.
        # Exercita backup/rollback com arquivos reais somente em TemporaryDirectory.
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            base = Path(temporary)
            root = base / 'opt/kit'; kit = base / 'entrada'
            (kit / 'tls').mkdir(parents=True)
            (kit / 'tls/servidor.key').write_bytes(b'CHAVE TLS FICTICIA DO TESTE')
            (kit / 'repo-chave-teste.gpg').write_bytes(b'CHAVE PUBLICA FICTICIA')
            (kit / 'config-homologacao.json').write_text('{"keys":{"teste":"publica"}}')
            config = base / 'etc/mainuan/atualizador-recursos.json'; config.parent.mkdir(parents=True)
            config.write_text('{"keys":{}}\n')
            prefs = base / 'etc/apt/preferences.d'; prefs.mkdir(parents=True)
            (prefs / 'original').write_bytes(b'preferencia original\n')
            (prefs.parent / 'preferences').write_bytes(b'preferencia unica original\n')
            hosts = base / 'etc/hosts'; hosts.write_bytes(b'127.0.0.1 localhost\n')
            (base / 'var/lib/apt/lists').mkdir(parents=True)
            original = {str(path): path.read_bytes() for path in (config, hosts, prefs / 'original', prefs.parent / 'preferences')}
            path_class = Path

            def mapped(value):
                value = str(value)
                return base / value.lstrip('/') if value.startswith(('/etc/', '/var/')) else path_class(value)

            for name, value in [('ROOT', root), ('CONFIG', config), ('PREF', prefs / '99-mainuan-homologacao-drivers'),
                                ('SOURCE', prefs.parent / 'sources.list.d/mainuan-homologacao-drivers.list'),
                                ('KEY', base / 'etc/apt/keyrings/mainuan-homologacao-drivers.gpg')]:
                stack.enter_context(patch.object(vm, name, value))
            stack.enter_context(patch.object(vm, 'Path', side_effect=mapped))
            stack.enter_context(patch.object(vm, 'verify_kit', return_value=({'id': 'test'}, Mock())))
            stack.enter_context(patch.object(vm, 'package_state', return_value={}))
            stack.enter_context(patch.object(vm, 'hardware_state', return_value={}))
            stack.enter_context(patch.object(vm, 'socket'))
            stack.enter_context(patch.object(vm.os, 'chown'))
            stack.enter_context(patch.object(vm, 'installed_modules'))
            stack.enter_context(patch.object(vm.subprocess, 'run'))
            stack.enter_context(patch('mainuan_recursos.packages.build_plan', return_value=Mock(blockers=(), pending=(Mock(),))))

            def command(args, **kwargs):
                if args[0] == 'apt-get' and '--simulate' in args:
                    return 'Inst nvidia-driver-test (1 test)\n' if fail_solver else 'Inst mainuan-gestao-drivers (1.0 test)\n'
                return ''

            stack.enter_context(patch.object(vm, 'run', side_effect=command))
            if fail_solver:
                with self.assertRaisesRegex(RuntimeError, 'além do gestor'):
                    vm.prepare(kit, 'snapshot-testado')
            else:
                vm.prepare(kit, 'snapshot-testado')
                self.assertEqual(config.read_bytes(), (kit / 'config-homologacao.json').read_bytes())
                self.assertEqual(vm.PREF.read_text(), vm.POLICY)
                vm.cleanup()
            for filename, data in original.items():
                self.assertEqual(Path(filename).read_bytes(), data)
            self.assertFalse(vm.SOURCE.exists())
            self.assertFalse(vm.KEY.exists())
            self.assertEqual(sorted(path.name for path in prefs.iterdir()), ['original'])

    def test_configuration_and_original_preferences_restore_exact_bytes(self):
        self.configuration_roundtrip()

    def test_unexpected_solver_changes_restore_original_configuration(self):
        self.configuration_roundtrip(fail_solver=True)
