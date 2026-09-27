"""Persistent, verified model storage. No network calls for a valid cache."""
import hashlib
import json
import os
from pathlib import Path

CATALOG = {
    'tiny': 'Systran/faster-whisper-tiny',
    'base': 'Systran/faster-whisper-base',
    'small': 'Systran/faster-whisper-small',
    'medium': 'Systran/faster-whisper-medium',
    'large-v3-turbo': 'mobiuslabsgmbh/faster-whisper-large-v3-turbo',
}
REVISIONS = {
    'tiny': 'd90ca5fe260221311c53c58e660288d3deb8d356',
    'base': 'ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66',
    'small': '536b0662742c02347bc0e980a01041f333bce120',
    'medium': '08e178d48790749d25932bbc082711ddcfdfbc4f',
    'large-v3-turbo': '0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf',
}
FILES = {'config.json', 'model.bin', 'tokenizer.json', 'vocabulary.json', 'vocabulary.txt', 'preprocessor_config.json'}
REQUIRED = {'config.json', 'model.bin', 'tokenizer.json'}


def data_root():
    if os.name == 'nt':
        return Path(os.environ['LOCALAPPDATA']) / 'TranscritorLocalPro'
    return Path(os.environ.get('TP3_DATA_DIR', Path.home() / '.local/share/TranscritorLocalPro'))


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def matches(path, record):
    if not path.is_file() or path.stat().st_size != record['size']:
        return False
    kind = record['algorithm']
    if kind not in ('sha256', 'git-sha1'):
        return False
    digest = hashlib.sha256() if kind == 'sha256' else hashlib.sha1()
    if kind == 'git-sha1':
        digest.update(f'blob {record["size"]}\0'.encode())
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest() == record['digest']


def valid_manifest(manifest, name):
    records = manifest.get('files', {})
    return (manifest.get('repo') == CATALOG[name]
            and isinstance(manifest.get('revision'), str)
            and manifest['revision'] == REVISIONS[name]
            and REQUIRED.issubset(records) and set(records).issubset(FILES)
            and all(isinstance(r.get('size'), int) and r['size'] > 0
                    and r.get('algorithm') in ('sha256', 'git-sha1')
                    and isinstance(r.get('digest'), str) for r in records.values()))


def metadata(name, revision=None):
    from huggingface_hub import HfApi
    info = HfApi().model_info(CATALOG[name], revision=revision or REVISIONS[name], files_metadata=True)
    records = {}
    for item in info.siblings:
        if item.rfilename not in FILES:
            continue
        lfs = item.lfs
        records[item.rfilename] = {
            'size': item.size,
            'algorithm': 'sha256' if lfs else 'git-sha1',
            'digest': lfs.sha256 if lfs else item.blob_id,
        }
    manifest = {'repo': CATALOG[name], 'revision': info.sha, 'files': records}
    if not valid_manifest(manifest, name):
        raise RuntimeError('Metadados do modelo incompletos.')
    return manifest


def download(repo, revision, filename, directory):
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(repo, filename, revision=revision,
                               local_dir=directory, force_download=True))


def ensure_model(name, root=None, report=lambda message: None, cancelled=lambda: False):
    from filelock import FileLock
    if name not in CATALOG:
        raise ValueError('Modelo não permitido.')
    directory = Path(root or data_root() / 'modelos') / name
    directory.mkdir(parents=True, exist_ok=True)
    with FileLock(str(directory / '.lock'), timeout=5):
        manifest_path = directory / 'manifest.json'
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if not valid_manifest(manifest, name):
                raise ValueError('Manifesto inválido')
        except (OSError, ValueError, TypeError, AttributeError):
            manifest = None
        report('Verificando integridade do modelo…')
        if manifest and all(matches(directory / f, r) for f, r in manifest['files'].items()):
            return directory
        if cancelled():
            raise InterruptedError('Cancelado.')
        # Reuse the pinned upstream revision for both first download and repair.
        manifest = metadata(name, manifest['revision'] if manifest else None)
        for filename, record in manifest['files'].items():
            if cancelled():
                raise InterruptedError('Cancelado.')
            target = directory / filename
            if matches(target, record):
                continue
            report(f'Baixando {name}/{filename}… (aguarde; cancelamento após o arquivo)')
            staged = download(manifest['repo'], manifest['revision'], filename, directory / '.download')
            if not matches(staged, record):
                raise RuntimeError(f'Falha de integridade: {filename}')
            os.replace(staged, target)
        atomic_json(manifest_path, manifest)
        return directory
