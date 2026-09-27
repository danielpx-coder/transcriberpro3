import hashlib
import json
from pathlib import Path
import pytest
from tp3 import models


def fixture_manifest():
    payloads = {name: ('sample-' + name).encode() for name in models.REQUIRED}
    manifest = {'repo': models.CATALOG['tiny'], 'revision': models.REVISIONS['tiny'], 'files': {}}
    for name, data in payloads.items():
        manifest['files'][name] = {'size': len(data), 'algorithm': 'sha256', 'digest': hashlib.sha256(data).hexdigest()}
    return payloads, manifest


def test_cache_offline_and_corruption_repair(tmp_path, monkeypatch):
    payloads, manifest = fixture_manifest()
    requests = []
    monkeypatch.setattr(models, 'metadata', lambda *args: manifest)
    def download(repo, revision, name, directory):
        requests.append(name)
        directory.mkdir(exist_ok=True)
        target = directory / name
        target.write_bytes(payloads[name])
        return target
    monkeypatch.setattr(models, 'download', download)
    path = models.ensure_model('tiny', tmp_path)
    assert len(requests) == len(payloads)
    def offline(*args):
        raise AssertionError('Cache válido não deve acessar a rede')
    monkeypatch.setattr(models, 'metadata', offline)
    monkeypatch.setattr(models, 'download', offline)
    assert models.ensure_model('tiny', tmp_path) == path
    (path / 'model.bin').write_bytes(b'bad model')
    monkeypatch.setattr(models, 'metadata', lambda *args: manifest)
    monkeypatch.setattr(models, 'download', download)
    models.ensure_model('tiny', tmp_path)
    assert requests.count('model.bin') == 2
    assert len(requests) == len(payloads) + 1


def test_invalid_download_never_promoted(tmp_path, monkeypatch):
    _, manifest = fixture_manifest()
    monkeypatch.setattr(models, 'metadata', lambda *args: manifest)
    bad = tmp_path / 'bad'
    bad.write_bytes(b'corrupt')
    monkeypatch.setattr(models, 'download', lambda *args: bad)
    with pytest.raises(RuntimeError, match='integridade'):
        models.ensure_model('tiny', tmp_path)
    assert not (tmp_path / 'tiny/manifest.json').exists()


def test_git_blob_checksum(tmp_path):
    data = b'example'
    path = tmp_path / 'config.json'
    path.write_bytes(data)
    assert models.matches(path, {'size': len(data), 'algorithm': 'git-sha1',
                                'digest': hashlib.sha1(b'blob 7\0' + data).hexdigest()})


def test_cache_manifest_cannot_escape_directory():
    _, manifest = fixture_manifest()
    manifest['files']['../escape'] = manifest['files']['model.bin']
    assert not models.valid_manifest(manifest, 'tiny')


def test_unknown_model_and_cancel(tmp_path):
    with pytest.raises(ValueError):
        models.ensure_model('../tiny', tmp_path)
    with pytest.raises(InterruptedError):
        models.ensure_model('tiny', tmp_path, cancelled=lambda: True)
