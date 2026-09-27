"""Opt-in model/inference smoke test; needs network on first run (~75 MB).
Run from repo root: python -m scripts.smoke-real --cache /tmp/tp3-models
Uses silence: validates execution, not speech recognition quality.
"""
import argparse
import socket
import tempfile
from pathlib import Path
import wave
from unittest.mock import patch
from tp3.engine import transcribe

parser = argparse.ArgumentParser()
parser.add_argument('--cache', type=Path, required=True)
args = parser.parse_args()
with tempfile.TemporaryDirectory() as folder:
    source = Path(folder) / 'silence.wav'
    with wave.open(str(source), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b'\0' * 32000)
    first = transcribe(source, model='tiny', device='cpu', root=args.cache, report=print)
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
        second = transcribe(source, model='tiny', device='cpu', root=args.cache, report=print)
    assert first['outputs'] == second['outputs']
    assert first['device'] == second['device'] == 'cpu'
    print('PASS: real CPU inference and repeated offline cache reuse (silence, not quality).')
