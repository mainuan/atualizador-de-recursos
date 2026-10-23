#!/usr/bin/python3
"""Prévia visual independente: não consulta catálogos nem modifica o sistema."""
import argparse
import configparser
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QDesktopServices, QIcon, QPalette
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFrame,
    QPlainTextEdit, QScrollArea,
    QVBoxLayout, QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mainuan_recursos.localization import install_pt_br, localize_standard_buttons

from mainuan_recursos.classic import ClassicContent, ILLUSTRATION, text_label
PROGRAMS = (
    ('Mainuan Gestão de Drivers', 'mainuan-gestao-drivers'),
    ('Boas-vindas do Mainuan', 'mainuan-boas-vindas'),
    ('Personalização do Mainuan', 'mainuan-personalizacao'),
)
ARTICLE = 'https://github.com/mainuan/atualizadorderecursos/releases'


class Preview(QDialog):
    def __init__(self, message, programs=PROGRAMS, illustration=ILLUSTRATION):
        super().__init__()
        self.setWindowTitle('Atualizador de Recursos do Mainuan — Prévia visual')
        self.setWindowIcon(QIcon(str(ROOT / 'data/mainuan-recursos.svg')))
        self.resize(720, 420)
        self.programs = tuple(programs)
        self.dialogs = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.view = ClassicContent(message, (name for name, _ in self.programs), illustration)
        outer.addWidget(self.view)
        for name in ('options', 'illustration', 'message', 'scroll', 'program_labels',
                     'know', 'install', 'later', 'buttons'):
            setattr(self, name, getattr(self.view, name))
        menu = self.view.menu
        menu.addAction('Verificar novidades', lambda: self.info('Verificar novidades',
            'Prévia visual: nenhuma consulta foi feita. Os programas são exemplos fictícios.'))
        menu.addAction('Histórico de novidades', lambda: self.info('Histórico de novidades',
            'Prévia visual: o histórico real permanece intacto.\n\n'
            'Exemplo: novidade visualizada, com recursos ainda não instalados.'))
        menu.addSeparator()
        menu.addAction('Informações técnicas', self.technical)
        self.know.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(ARTICLE)))
        self.install.clicked.connect(self.confirmation)
        self.later.clicked.connect(lambda: self.info('Agora não',
            'No aplicativo, esta ação adia a notificação por 24 horas.\n\n'
            'Esta prévia não altera o histórico ou os adiamentos.'))

    def info(self, title, message):
        dialog = self.make_dialog(title, compact=True)
        dialog.layout().addWidget(text_label(message))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        localize_standard_buttons(buttons)
        buttons.rejected.connect(dialog.reject)
        dialog.layout().addWidget(buttons)
        dialog.open()
        return dialog

    def make_dialog(self, title, compact=False):
        dialog = QDialog(self)
        dialog.setWindowTitle(title + ' — Prévia visual')
        QVBoxLayout(dialog)
        dialog.resize(min(460 if compact else 520, self.width() - 24),
                      min(160 if compact else 360, self.height() - 24))
        self.dialogs.append(dialog)
        dialog.finished.connect(lambda: self.dialogs.remove(dialog))
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        return dialog

    def technical(self):
        dialog = self.make_dialog('Informações técnicas')
        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText('Dados fictícios para avaliar a apresentação.\n\n' + '\n'.join(
            f'{name}\n  Pacote: {package}\n  Versão oferecida: 1.0\n'
            '  Instalada: não consultada\n  Dependências: não consultadas\n'
            for name, package in self.programs))
        dialog.layout().addWidget(details)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        localize_standard_buttons(buttons)
        buttons.rejected.connect(dialog.reject)
        dialog.layout().addWidget(buttons)
        dialog.open()
        return dialog

    def confirmation(self):
        dialog = self.make_dialog('Confirmar instalação')
        dialog.layout().addWidget(text_label('Deseja receber estas novidades do Mainuan?'))
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(50)
        content = QWidget()
        content.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        items = QVBoxLayout(content)
        for name, _package in self.programs:
            items.addWidget(text_label('•  ' + name))
        items.addStretch()
        scroll.setWidget(content)
        dialog.layout().addWidget(scroll, 1)
        dialog.layout().addWidget(text_label(
            'Prévia visual: nenhuma instalação ou autorização administrativa será iniciada.'))
        buttons = QDialogButtonBox()
        simulate = buttons.addButton('Simular conclusão', QDialogButtonBox.ButtonRole.AcceptRole)
        cancel = buttons.addButton('Cancelar', QDialogButtonBox.ButtonRole.RejectRole)
        cancel.setDefault(True)
        simulate.setAutoDefault(False)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog.layout().addWidget(buttons)
        simulate.clicked.connect(lambda: QTimer.singleShot(0, lambda: self.info(
            'Simulação concluída', 'Demonstração encerrada. Nenhum pacote foi instalado.')))
        dialog.open()
        return dialog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--message-file', type=Path, default=ROOT / 'message.txt')
    parser.add_argument('--size', default='720x420', help='dimensões lógicas Qt, por exemplo 640x480')
    parser.add_argument('--long-list', action='store_true', help='demonstrar 12 programas com nomes longos')
    parser.add_argument('--scheme', type=Path, help='paleta KDE aplicada somente à prévia')
    parser.add_argument('--capture-dir', type=Path, help='captura e verifica a prévia, depois encerra')
    opts = parser.parse_args()
    try:
        width, height = map(int, opts.size.split('x'))
        if width < 380 or height < 280:
            raise ValueError()
    except ValueError:
        parser.error('Use largura x altura de pelo menos 380x280 pixels lógicos.')
    private = None
    expected = None
    if opts.scheme:
        scheme = opts.scheme.read_text()
        config = configparser.ConfigParser(interpolation=None)
        config.read_string(scheme)
        rgb = config['Colors:Window']['BackgroundNormal'].split(',')[:3]
        expected = '#' + ''.join(f'{int(value):02x}' for value in rgb)
        private = tempfile.TemporaryDirectory(prefix='mainuan-previa-paleta-')
        os.environ['XDG_CONFIG_HOME'] = private.name
        scheme = scheme.replace('[General]', f'[General]\nColorScheme={opts.scheme.stem}', 1)
        Path(private.name, 'kdeglobals').write_text(scheme + '\n[KDE]\nwidgetStyle=Breeze\n')
    started = time.monotonic()
    app = QApplication([])
    app.setApplicationName('mainuan-previa-classica')
    native_translations = install_pt_br(app)
    programs = PROGRAMS
    if opts.long_list:
        programs += tuple((f'Programa de exemplo {i:02d} — Ferramentas de acessibilidade, '
            'personalização e integração com a área de trabalho do Mainuan', f'exemplo-{i}')
            for i in range(4, 13))
    window = Preview(opts.message_file.read_text().strip(), programs=programs)
    window.resize(width, height)
    window.show()
    report = {}
    if opts.capture_dir:
        opts.capture_dir.mkdir(parents=True, exist_ok=True)

        def capture():
            rects = [QRectF(button.rect().translated(button.mapTo(window, button.rect().topLeft())))
                     for button in window.buttons]
            memory = Path('/proc/self/smaps_rollup').read_text()
            color = app.palette().color(QPalette.ColorRole.Window).name()
            report.update(platform=app.platformName(), style=app.style().objectName(),
                window_color=color, scheme_matches=expected is None or color == expected,
                requested_size=[width, height], actual_size=[window.width(), window.height()],
                size_not_expanded=window.width() <= width and window.height() <= height,
                compositor_constrained=[window.width(), window.height()] != [width, height],
                available_screen=[window.screen().availableGeometry().width(),
                                  window.screen().availableGeometry().height()],
                device_pixel_ratio=window.devicePixelRatioF(), ready_ms=round((time.monotonic()-started)*1000),
                buttons_inside=all(QRectF(window.rect()).contains(rect) for rect in rects),
                buttons_aligned=len({rect.right() for rect in rects}) == 1,
                buttons_equal_size=len({(rect.width(), rect.height()) for rect in rects}) == 1,
                buttons_below_content=window.scroll.mapTo(window, window.scroll.rect().bottomLeft()).y()
                    < rects[0].top(),
                message_plain=window.message.textFormat() == Qt.TextFormat.PlainText,
                program_names_not_clipped=all(item.height() >= item.heightForWidth(item.width())
                                              for item in window.program_labels),
                programs=len(window.program_labels), illustration_inside=QRectF(window.illustration.rect()).contains(
                    window.illustration.image_rect()),
                illustration_file=ILLUSTRATION.name,
                illustration_alpha=window.illustration.pixmap.hasAlphaChannel(),
                qt_translation_loaded=native_translations,
                horizontal_scroll=window.scroll.horizontalScrollBar().maximum(),
                vertical_scroll=window.scroll.verticalScrollBar().maximum(),
                memory_kib={line.split(':')[0]:int(line.split()[1]) for line in memory.splitlines()
                            if line.startswith(('Rss:', 'Pss:'))})
            window.grab().save(str(opts.capture_dir / 'principal.png'))
            window.scroll.verticalScrollBar().setValue(window.scroll.verticalScrollBar().maximum())
            app.processEvents()
            last = window.program_labels[-1]
            report['last_program_reachable'] = window.scroll.viewport().rect().contains(
                last.rect().translated(last.mapTo(window.scroll.viewport(), last.rect().topLeft())))
            if report['vertical_scroll']:
                window.grab().save(str(opts.capture_dir / 'programas-apos-rolagem.png'))
            reachable = []
            for item in window.program_labels:
                window.scroll.ensureWidgetVisible(item, 0, 0)
                app.processEvents()
                reachable.append(window.scroll.viewport().rect().contains(
                    item.rect().translated(item.mapTo(window.scroll.viewport(), item.rect().topLeft()))))
            report['all_programs_reachable'] = all(reachable)
            window.scroll.verticalScrollBar().setValue(0)
            details = window.technical()

            def capture_details():
                details.grab().save(str(opts.capture_dir / 'detalhes.png'))
                details.reject()
                confirmation = window.confirmation()
                QTimer.singleShot(100, lambda: finish(confirmation))

            QTimer.singleShot(100, capture_details)

        def finish(confirmation):
            confirmation.grab().save(str(opts.capture_dir / 'confirmacao.png'))
            confirmation.reject()
            window.later.click()
            later = window.dialogs[-1]
            close = later.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Close)
            report['close_text'] = close.text().replace('&', '')
            QTimer.singleShot(100, lambda: finish_later(later, close))

        def finish_later(later, close):
            later.grab().save(str(opts.capture_dir / 'agora-nao.png'))
            close.click()
            (opts.capture_dir / 'resultado.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
            app.quit()

        QTimer.singleShot(400, capture)
    app.exec()
    if private:
        private.cleanup()
    if report:
        print(json.dumps(report, ensure_ascii=False))
        return 0 if all(report[key] for key in ('scheme_matches', 'buttons_inside',
            'buttons_aligned', 'buttons_equal_size', 'message_plain', 'illustration_inside',
            'illustration_alpha', 'last_program_reachable', 'size_not_expanded',
            'buttons_below_content', 'program_names_not_clipped', 'all_programs_reachable')) \
            and report['horizontal_scroll'] == 0 and report['close_text'] == 'Fechar' else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
