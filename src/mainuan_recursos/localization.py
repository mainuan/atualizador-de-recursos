"""Tradução nativa do Qt para pt_BR, com alternativa para botões padrão."""
from PyQt6.QtCore import QCoreApplication, QEvent, QLibraryInfo, QLocale, QObject, QTranslator
from PyQt6.QtWidgets import QDialogButtonBox, QMessageBox


_BUTTON_LABELS = {
    'Ok': ('OK', 'OK'), 'Close': ('Close', 'Fechar'), 'Cancel': ('Cancel', 'Cancelar'),
    'Yes': ('&Yes', '&Sim'), 'No': ('&No', '&Não'),
    'YesToAll': ('Yes to &All', 'Sim para &todos'), 'NoToAll': ('N&o to All', 'Não para todos'),
    'Save': ('Save', 'Salvar'), 'SaveAll': ('Save All', 'Salvar tudo'),
    'Open': ('Open', 'Abrir'), 'Discard': ('Discard', 'Descartar'),
    'Apply': ('Apply', 'Aplicar'), 'Reset': ('Reset', 'Redefinir'),
    'RestoreDefaults': ('Restore Defaults', 'Restaurar padrões'),
    'Help': ('Help', 'Ajuda'), 'Abort': ('Abort', 'Interromper'),
    'Retry': ('Retry', 'Tentar novamente'), 'Ignore': ('Ignore', 'Ignorar'),
}

def localize_standard_buttons(box):
    """Cobre catálogos ausentes e textos ingleses fornecidos pelo tema KDE."""
    for name, (source, fallback) in _BUTTON_LABELS.items():
        button = box.button(getattr(box.StandardButton, name))
        if button is None or button.text().replace('&', '') != source.replace('&', ''):
            continue
        translated = QCoreApplication.translate('QPlatformTheme', source)
        button.setText(fallback if translated.replace('&', '') == source.replace('&', '') else translated)


class _ButtonLocalizer(QObject):
    def stop(self):
        # Retira o filtro Python antes da destruição dos objetos Qt/Wayland.
        self.parent().removeEventFilter(self)

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.Show and isinstance(widget, (QDialogButtonBox, QMessageBox)):
            localize_standard_buttons(widget)
        return False


def install_pt_br(app, translations_directory=None):
    """Usa qtbase_pt_BR; só corrige rótulos ingleses, preservando papéis/sinais."""
    previous = getattr(app, '_mainuan_button_localizer', None)
    if previous is not None:
        app.removeEventFilter(previous)
        previous.deleteLater()
    for translator in getattr(app, '_mainuan_translators', ()):
        app.removeTranslator(translator)
        translator.deleteLater()
    QLocale.setDefault(QLocale('pt_BR'))
    native = QTranslator(app)
    directory = (translations_directory if translations_directory is not None else
                 QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    loaded = native.load('qtbase_pt_BR', str(directory))
    if loaded:
        app.installTranslator(native)
    # Mantém referências Python durante todo o ciclo da aplicação.
    app._mainuan_translators = (native,)
    app._mainuan_button_localizer = _ButtonLocalizer(app)
    app.installEventFilter(app._mainuan_button_localizer)
    app.aboutToQuit.connect(app._mainuan_button_localizer.stop)
    return loaded
