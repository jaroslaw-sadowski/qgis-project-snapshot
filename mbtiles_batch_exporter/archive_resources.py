"""Copy known project resources and report dependencies requiring review."""
from .i18n import tr
from hashlib import sha256
import os
from pathlib import Path
import re
import shutil
import time
import xml.etree.ElementTree as ET

from qgis.core import QgsApplication, QgsVectorLayer


class ProjectResources:
    def __init__(self, project, folder, cancelled, progress):
        self.project = project
        self.folder = folder
        self.cancelled = cancelled
        self.progress = progress
        self.files = {}
        self.issues = []

    def issue(self, owner, reason):
        entry = {'owner': owner, 'reason': reason}
        if entry not in self.issues:
            self.issues.append(entry)

    def copy(self, value, owner, base=None):
        if not value or value.startswith(('base64:', 'data:', ':/')):
            return value
        if self.cancelled():
            self.issue(owner, tr('Przerwano kopiowanie zasobów.'))
            return value
        if re.match(r'^https?://', value, re.I):
            self.issue(owner, tr('Zasób internetowy wymaga ręcznego zapisania i sprawdzenia.'))
            return value
        if value.startswith('attachment:'):
            resolved = self.project.resolveAttachmentIdentifier(value)
            path = Path(resolved) if resolved else None
        else:
            path = Path(value.removeprefix('file://'))
            if not path.is_absolute():
                path = (Path(base) if base else Path(self.project.homePath() or '.')) / path
            if not path.is_file():
                # Native QGIS symbols can be relative to an installed SVG library.
                path = next((Path(root) / value for root in QgsApplication.svgPaths()
                             if (Path(root) / value).is_file()), path)
        if path is None or not path.is_file():
            self.issue(owner, tr('Nie znaleziono lokalnego pliku zasobu.'))
            return value
        path = path.resolve()
        if path in self.files:
            return self.files[path]
        self.progress(tr('Kopiowanie zasobów: {0}').format(owner))
        digest = sha256(str(path).encode()).hexdigest()[:20]
        target = self.folder / 'zasoby' / digest / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open('rb') as source, target.open('wb') as output:
                updated = time.monotonic()
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    if self.cancelled():
                        self.issue(owner, tr('Przerwano kopiowanie zasobów.'))
                        break
                    output.write(chunk)
                    if time.monotonic() - updated > 0.1:
                        self.progress(tr('Kopiowanie zasobów: {0}').format(owner))
                        updated = time.monotonic()
                else:
                    shutil.copystat(path, target)
            if self.cancelled():
                target.unlink(missing_ok=True)
                return value
        except OSError:
            target.unlink(missing_ok=True)
            self.issue(owner, tr('Nie udało się skopiować pliku zasobu.'))
            return value
        relative = './' + target.relative_to(self.folder).as_posix()
        self.files[path] = relative
        if target.suffix.lower() in ('.svg', '.ui'):
            try:
                tree = ET.parse(target)
                for node in tree.iter():
                    for key, reference in list(node.attrib.items()):
                        if key.endswith('href') and reference and not reference.startswith('#'):
                            copied = self.copy(reference, owner, path.parent)
                            if copied.startswith('./zasoby/'):
                                node.set(key, os.path.relpath(self.folder / copied[2:], target.parent))
                    if node.tag in ('pixmap', 'iconset') and node.text and node.text.strip():
                        copied = self.copy(node.text.strip(), owner, path.parent)
                        if copied.startswith('./zasoby/'):
                            node.text = os.path.relpath(self.folder / copied[2:], target.parent)
                    if node.tag in ('customwidgets', 'resources') and len(node):
                        self.issue(owner, tr('Formularz używa dodatkowych komponentów Qt; wymaga sprawdzenia.'))
                tree.write(target, encoding='utf-8', xml_declaration=True)
            except (ET.ParseError, OSError):
                self.issue(owner, tr('Nie udało się sprawdzić odwołań wewnątrz SVG lub formularza.'))
        return relative

    def attachments(self, element, record):
        if record['method'] != 'vector':
            return
        for field in element.findall('./fieldConfiguration/field'):
            widget = field.find('editWidget')
            if widget is None or widget.get('type') != 'ExternalResource':
                continue
            options = {n.get('name'): n for n in widget.iter('Option')}
            root = options.get('DefaultRoot')
            base = root.get('value') if root is not None else None
            if base and not Path(base).is_absolute():
                base = str(Path(self.project.homePath()) / base)
            layer = QgsVectorLayer(str(self.folder / record['local_source'][2:]), record['name'], 'ogr')
            index = layer.fields().indexFromName(field.get('name'))
            if not layer.isValid() or index < 0 or not layer.startEditing():
                self.issue(record['name'], tr('Nie udało się przepisać odwołań do załączników.'))
                continue
            try:
                for feature in layer.getFeatures():
                    if self.cancelled():
                        self.issue(record['name'], tr('Przerwano kopiowanie załączników.'))
                        break
                    value = feature[index]
                    if isinstance(value, str) and value:
                        copied = self.copy(value, record['name'], base)
                        if copied != value and not layer.changeAttributeValue(feature.id(), index, copied):
                            raise RuntimeError(tr('Nie udało się zapisać ścieżki załącznika.'))
                if not layer.commitChanges():
                    raise RuntimeError(tr('Nie udało się zapisać ścieżek załączników.'))
            finally:
                if layer.isEditable():
                    layer.rollBack()
            # Resolve saved relative paths against the archive project directory.
            if root is not None:
                root.set('value', '')
            relative = options.get('RelativeStorage')
            if relative is not None:
                relative.set('value', '1')

    def rewrite(self, root, records):
        saved = {r['id']: r for r in records if r.get('local_source')}
        vectors = {key for key, record in saved.items() if record['method'] == 'vector'}
        relations = root.find('relations')
        valid_relations = set()
        if relations is not None:
            for relation in list(relations):
                if relation.get('referencingLayer') in vectors and relation.get('referencedLayer') in vectors:
                    valid_relations.add(relation.get('id'))
                    self.issue(relation.get('name') or 'Relacja', tr('Relacja zachowana; obszar eksportu może pomijać powiązane obiekty poza obszarem.'))
                else:
                    relations.remove(relation)
                    self.issue('Relacje', tr('Usunięto relację do warstwy niezapisanej jako dane wektorowe.'))
        for element in root.findall('./projectlayers/maplayer'):
            record = saved.get(element.findtext('id'))
            if not record:
                continue
            owner = record['name']
            self.attachments(element, record)
            for widget in element.findall('.//editWidget'):
                options = {n.get('name'): n.get('value') for n in widget.iter('Option')}
                missing = ((widget.get('type') == 'ValueRelation' and options.get('Layer') not in vectors)
                           or (widget.get('type') == 'RelationReference' and options.get('Relation') not in valid_relations))
                if missing:
                    widget.set('type', 'TextEdit')
                    for child in list(widget):
                        widget.remove(child)
                    self.issue(owner, tr('Pole formularza wskazywało brakującą relację; pozostawiono odczyt wartości.'))
            for parent in element.iter():
                for child in list(parent):
                    if child.tag == 'attributeEditorRelation' and child.get('relation') not in valid_relations:
                        parent.remove(child)
            for tag in ('editform', 'editforminitfilepath'):
                for node in element.findall(tag):
                    if node.text and node.text.strip():
                        node.text = self.copy(node.text.strip(), owner)
            # QGIS stores example Python code even when no init function is enabled.
            if (element.findtext('editforminit') or '').strip():
                self.issue(owner, tr('Kod formularza wymaga ręcznej kontroli zależności.'))
            if element.findall('./attributeactions/actionsetting'):
                self.issue(owner, tr('Akcje warstwy mogą uruchamiać zewnętrzne zasoby; wymagają kontroli.'))
            for symbol in element.findall('.//layer'):
                kind = symbol.get('class', '').lower()
                if any(word in kind for word in ('svg', 'raster')):
                    for option in symbol.iter('Option'):
                        if option.get('name') in ('name', 'imageFile', 'svgFile', 'file') and option.get('value'):
                            option.set('value', self.copy(option.get('value'), owner))
                    for prop in symbol.findall('prop'):
                        if prop.get('k') in ('name', 'imageFile', 'svgFile', 'file'):
                            prop.set('v', self.copy(prop.get('v', ''), owner))
        for node in root.iter():
            if node.tag == 'LayoutItem' and node.get('file'):
                node.set('file', self.copy(node.get('file'), tr('Układ wydruku')))
            if node.tag == 'Option' and node.get('name') == 'expression' and node.get('value'):
                self.issue(tr('Wyrażenia'), tr('Projekt zawiera wyrażenia dynamiczne; ich zależności wymagają kontroli.'))
            if node.tag == 'LayoutItem' and (node.get('html') or node.get('url')):
                self.issue(tr('Układ wydruku'), tr('Element HTML wymaga kontroli zewnętrznych zasobów.'))
        if root.findall('.//Layout'):
            self.issue(tr('Układy wydruku'), tr('Układy i atlas wymagają odbioru wizualnego po ograniczeniu danych do obszaru.'))
        if root.findall('./polymorphicRelations/relation'):
            self.issue('Relacje', tr('Relacje polimorficzne wymagają ręcznej kontroli.'))
        return {'copied_files': len(self.files), 'issues': self.issues}


def audit_local_layers(project_file, records):
    """Resolve only known local sources; never reopen original network providers."""
    from qgis.core import QgsProject
    project = QgsProject()
    failures = []
    try:
        if not project.read(str(project_file)):
            return [tr('Nie można otworzyć projektu archiwalnego.')]
        for record in records:
            if not record.get('local_source'):
                continue
            layer = project.mapLayer(record['id'])
            if layer is None or not layer.isValid():
                failures.append(tr('Nie można otworzyć lokalnej warstwy: {0}').format(record["name"]))
        return failures
    finally:
        project.clear()
