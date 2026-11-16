"""Qt translations for the session language, with a fallback for standard buttons.

The language is never forced: ``qtbase_<lang>`` is loaded for ``QLocale.system()``
(which follows LANGUAGE/LC_ALL/LC_MESSAGES/LANG), and the application strings come
from the gettext catalog (see ``i18n``).
"""
from PyQt6.QtCore import QCoreApplication, QEvent, QLibraryInfo, QLocale, QObject, QTranslator
from PyQt6.QtWidgets import QDialogButtonBox, QMessageBox

from .i18n import pgettext


def _fallback_labels():
    """English source label -> label from the application catalog.

    Used only when neither qtbase_<lang>.qm nor the platform theme translated a
    standard button (missing catalog, or English labels supplied by the theme).
    """
    return {
        'Ok': ('OK', pgettext('standard button', 'OK')),
        'Close': ('Close', pgettext('standard button', 'Close')),
        'Cancel': ('Cancel', pgettext('standard button', 'Cancel')),
        'Yes': ('&Yes', pgettext('standard button', '&Yes')),
        'No': ('&No', pgettext('standard button', '&No')),
        'YesToAll': ('Yes to &All', pgettext('standard button', 'Yes to &All')),
        'NoToAll': ('N&o to All', pgettext('standard button', 'No to All')),
        'Save': ('Save', pgettext('standard button', 'Save')),
        'SaveAll': ('Save All', pgettext('standard button', 'Save All')),
        'Open': ('Open', pgettext('standard button', 'Open')),
        'Discard': ('Discard', pgettext('standard button', 'Discard')),
        'Apply': ('Apply', pgettext('standard button', 'Apply')),
        'Reset': ('Reset', pgettext('standard button', 'Reset')),
        'RestoreDefaults': ('Restore Defaults', pgettext('standard button', 'Restore Defaults')),
        'Help': ('Help', pgettext('standard button', 'Help')),
        'Abort': ('Abort', pgettext('standard button', 'Abort')),
        'Retry': ('Retry', pgettext('standard button', 'Retry')),
        'Ignore': ('Ignore', pgettext('standard button', 'Ignore')),
    }


def localize_standard_buttons(box):
    """Translate standard buttons still showing their English label.

    Native Qt translation (qtbase) has priority; the application catalog is the
    fallback.  Custom labels are never touched, so roles and signals are kept.
    """
    for name, (source, fallback) in _fallback_labels().items():
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


def install_translations(app, translations_directory=None, locale=None):
    """Load qtbase for the session locale; only fix standard buttons left in English.

    Returns True when the native Qt catalog for the session language was loaded.
    """
    previous = getattr(app, '_mainuan_button_localizer', None)
    if previous is not None:
        app.removeEventFilter(previous)
        previous.deleteLater()
    for translator in getattr(app, '_mainuan_translators', ()):
        app.removeTranslator(translator)
        translator.deleteLater()
    native = QTranslator(app)
    directory = (translations_directory if translations_directory is not None else
                 QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    loaded = native.load(locale if locale is not None else QLocale.system(), 'qtbase', '_', str(directory))
    if loaded:
        app.installTranslator(native)
    # Mantém referências Python durante todo o ciclo da aplicação.
    app._mainuan_translators = (native,)
    app._mainuan_button_localizer = _ButtonLocalizer(app)
    app.installEventFilter(app._mainuan_button_localizer)
    app.aboutToQuit.connect(app._mainuan_button_localizer.stop)
    return loaded
