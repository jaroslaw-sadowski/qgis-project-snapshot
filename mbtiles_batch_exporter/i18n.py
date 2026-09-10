"""Qt translation catalog, using the QGIS locale override before the OS locale."""
import os
from pathlib import Path
from qgis.PyQt.QtCore import QLocale, QTranslator
from qgis.core import QgsSettings

_translator = None


def language():
    worker_locale = os.environ.get('QGIS_SNAPSHOT_LANGUAGE')
    if worker_locale in ('en', 'pl'):
        return worker_locale
    settings = QgsSettings()
    locale = (settings.value('locale/userLocale', 'en')
              if settings.value('locale/overrideFlag', False, type=bool)
              else QLocale().name())
    return 'pl' if str(locale).lower().startswith('pl') else 'en'


def tr(message):
    global _translator
    if language() == 'pl':
        return message
    if _translator is None:
        _translator = QTranslator()
        _translator.load(str(Path(__file__).with_name('en.qm')))
    return _translator.translate('qgis-project-snapshot', message.encode('utf-8')) or message
