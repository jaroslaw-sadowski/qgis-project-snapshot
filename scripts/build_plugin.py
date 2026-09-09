"""Build a reproducible QGIS plugin ZIP using only the Python standard library."""
import argparse
import ast
from configparser import ConfigParser
from hashlib import sha256
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]


def build(output):
    package = ROOT / 'mbtiles_batch_exporter'
    metadata = ConfigParser()
    metadata.read(package / 'metadata.txt', encoding='utf-8')
    version = metadata['general']['version']
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}', version):
        raise ValueError('Nieprawidłowa wersja w metadata.txt.')
    sources = {path.name: path for path in package.glob('*.py')}
    sources.update({name: package / name for name in ('metadata.txt', 'icon.png', 'README.txt')})
    sources.update({'LICENSE': ROOT / 'LICENSE', 'INSTRUKCJA.md': ROOT / 'docs' / 'team-guide.md'})
    for name, path in sources.items():
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Brak zwykłego pliku paczki: {name}')
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8'), filename=name)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f'mbtiles_batch_exporter-{version}.zip'
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, path in sorted(sources.items()):
            info = ZipInfo(f'mbtiles_batch_exporter/{name}', date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    checksum = sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.zip.sha256').write_text(f'{checksum}  {destination.name}\n', encoding='ascii')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    print(build(parser.parse_args().output))
