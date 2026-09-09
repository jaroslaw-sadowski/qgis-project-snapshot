"""Native QGIS checks for portable symbols, attachments and relations."""
import json
from pathlib import Path
import shutil
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from qgis.core import QgsEditorWidgetSetup, QgsProject, QgsRelation, QgsRelationContext, QgsSvgMarkerSymbolLayer

import test_archive as fixtures
from mbtiles_batch_exporter.archive_resources import ProjectResources
from mbtiles_batch_exporter.raster_archive import _render_image


class ResourceTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    tearDown = fixtures.ArchiveTests.tearDown
    add_points = fixtures.ArchiveTests.add_points
    archive = fixtures.ArchiveTests.archive
    manifest = fixtures.ArchiveTests.manifest

    def test_svg_attachment_and_form_survive_move_and_source_deletion(self):
        source = self.folder / 'source'
        source.mkdir()
        svg = source / 'symbol.svg'
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><circle cx="10" cy="10" r="9" fill="red"/></svg>')
        document = source / 'opis.txt'
        document.write_text('Stan dokumentacji w dniu archiwizacji')
        form = source / 'form.ui'
        form.write_text('<ui version="4.0"><class>Form</class><widget class="QWidget" name="Form"/></ui>')
        attached = Path(self.project.createAttachedFile('embedded.txt'))
        attached.write_text('Osadzony załącznik')
        self.layer.renderer().symbol().changeSymbolLayer(0, QgsSvgMarkerSymbolLayer(str(svg)))
        config = self.layer.editFormConfig()
        config.setUiForm(str(form))
        self.layer.setEditFormConfig(config)
        self.layer.setEditorWidgetSetup(1, QgsEditorWidgetSetup('ExternalResource', {'DefaultRoot': str(source), 'RelativeStorage': 2}))
        self.layer.startEditing()
        for feature in self.layer.getFeatures():
            self.layer.changeAttributeValue(feature.id(), 1, 'opis.txt')
        result = self.archive()
        manifest = self.manifest(result)
        self.assertEqual(manifest['resources']['copied_files'], 3, manifest['resources'])
        self.assertEqual(manifest['resources']['issues'], [])
        self.assertTrue(manifest['local_layer_audit']['passed'])
        self.project.clear()
        shutil.rmtree(source)
        moved = self.folder / 'przeniesione'
        shutil.move(result, moved)
        project = QgsProject()
        try:
            self.assertTrue(project.read(str(next(moved.glob('*.qgz')))))
            layer = next(iter(project.mapLayers().values()))
            self.assertTrue(layer.isValid())
            self.assertTrue(Path(layer.renderer().symbol().symbolLayer(0).path()).is_file())
            self.assertTrue(Path(layer.editFormConfig().uiForm()).is_file())
            image = _render_image(layer, project, self.area.boundingBox(), 256, 256, lambda: False, lambda text: None)
            self.assertTrue(any(image.pixelColor(x, y).red() > 200 and image.pixelColor(x, y).green() < 100
                                and image.pixelColor(x, y).alpha() > 0 for x in range(256) for y in range(256)))
            self.assertIn('Osadzony załącznik', [Path(path).read_text() for path in project.attachedFiles() if path.endswith('.txt')])
            for feature in layer.getFeatures():
                self.assertEqual((moved / feature['opis']).read_text(), 'Stan dokumentacji w dniu archiwizacji')
        finally:
            project.clear()

    def test_missing_relation_is_removed_but_valid_relation_preserved(self):
        second = self.add_points('Druga', [(5, 5)])
        relation = QgsRelation(QgsRelationContext(self.project))
        relation.setId('test_relation')
        relation.setName('Relacja testowa')
        relation.setReferencingLayer(second.id())
        relation.setReferencedLayer(self.layer.id())
        relation.addFieldPair('fid', 'fid')
        self.project.relationManager().addRelation(relation)
        second.setEditorWidgetSetup(0, QgsEditorWidgetSetup('RelationReference', {'Relation': 'test_relation'}))
        complete = self.archive()
        missing = self.archive([second.id()])
        for folder, expected in ((complete, 1), (missing, 0)):
            with ZipFile(next(folder.glob('*.qgz'))) as archive:
                root = ET.fromstring(archive.read(next(n for n in archive.namelist() if n.endswith('.qgs'))))
            self.assertEqual(len(root.findall('./relations/relation')), expected)
        self.assertTrue(self.manifest(missing)['resources']['issues'])
        widgets = root.findall('.//editWidget')
        self.assertNotIn('RelationReference', [w.get('type') for w in widgets])

    def test_remote_missing_and_dynamic_dependencies_are_reported(self):
        root = ET.fromstring('''<qgis><projectlayers><maplayer><id>one</id><renderer-v2><symbols><symbol>
          <layer class="SvgMarker"><Option><Option name="name" value="https://example.invalid/symbol.svg"/></Option></layer>
          </symbol></symbols></renderer-v2><editform>/missing/form.ui</editform>
          <editforminit>initialize</editforminit><editforminitcode>external_dependency()</editforminitcode></maplayer></projectlayers>
          <Option name="expression" value="file_exists('remote')"/></qgis>''')
        resources = ProjectResources(self.project, self.folder, lambda: False, lambda text: None)
        report = resources.rewrite(root, [{'id': 'one', 'name': 'Test', 'method': 'raster_render', 'local_source': './test'}])
        self.assertEqual(report['copied_files'], 0)
        self.assertEqual(len(report['issues']), 4)
        self.assertNotIn('https://', json.dumps(report))


if __name__ == '__main__':
    unittest.main()
