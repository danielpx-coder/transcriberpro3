import sys
from types import SimpleNamespace
import pytest
from tp3 import engine


def test_gpu_failure_restarts_cpu_without_duplicate_segments(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, 'ensure_model', lambda *args: tmp_path)
    monkeypatch.setitem(sys.modules, 'ctranslate2', SimpleNamespace(get_cuda_device_count=lambda: 1))
    seen = []
    class Fake:
        def __init__(self, path, device, **kwargs):
            self.device = device
            seen.append(device)
        def transcribe(self, *args, **kwargs):
            def generate():
                yield SimpleNamespace(start=0, end=1, text='teste')
                if self.device == 'cuda': raise RuntimeError('missing cudnn')
            return generate(), SimpleNamespace(duration=1, language='pt')
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=Fake))
    result = engine.transcribe('x')
    assert seen == ['cuda', 'cpu']
    assert result['device'] == 'cpu'
    assert len(result['segments']) == 1


def test_cancel_before_inference(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, 'ensure_model', lambda *args: tmp_path)
    with pytest.raises(InterruptedError):
        engine.transcribe('x', cancelled=lambda: True)
