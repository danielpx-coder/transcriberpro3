"""Preserve installed distribution metadata and bundled license files."""
import importlib.metadata
from pathlib import Path
import shutil
import sys

target = Path(sys.argv[1])
target.mkdir(parents=True, exist_ok=True)
for distribution in importlib.metadata.distributions():
    name = distribution.metadata['Name']
    out = target / name
    out.mkdir(exist_ok=True)
    (out / 'METADATA.txt').write_text(distribution.read_text('METADATA') or '', encoding='utf-8')
    for file in distribution.files or []:
        if any(term in file.name.lower() for term in ('license', 'copying', 'notice')):
            source = Path(distribution.locate_file(file))
            if source.is_file():
                destination = out / str(file).replace('..', '_').replace('/', '_').replace('\\', '_')
                shutil.copyfile(source, destination)
