import json
import threading
import time
from fastapi.testclient import TestClient
from filelock import Timeout
import pytest
from server.app import create_app, Store

TOKEN = 'test-only-' + 'x' * 40
HEADERS = {'Authorization': 'Bearer ' + TOKEN, 'X-TP3-Owner': '1'}


def wait(client, job, states=('done',)):
    for _ in range(150):
        response = client.get('/jobs/' + job, headers=HEADERS)
        if response.json()['state'] in states: return response.json()
        time.sleep(.02)
    raise AssertionError('Worker did not finish')


def fake(source, **kwargs):
    assert source.read_bytes() == b'audio'
    kwargs['progress'](80)
    return {'outputs': {'txt': 'Olá', 'srt': '', 'vtt': 'WEBVTT\n'}, 'device': 'cpu'}


def test_auth_upload_owner_result_and_cleanup(tmp_path):
    with TestClient(create_app(tmp_path, TOKEN, fake, max_bytes=8)) as client:
        assert client.post('/jobs', content=b'audio').status_code == 401
        assert client.post('/jobs', headers=HEADERS, content=b'x' * 9).status_code == 413
        assert client.post('/jobs', headers=HEADERS, content=b'').status_code == 400
        assert client.post('/jobs?model=medium', headers=HEADERS, content=b'audio').status_code == 400
        response = client.post('/jobs', headers=HEADERS, content=b'audio')
        assert response.status_code == 202
        job = response.json()['id']
        other = {**HEADERS, 'X-TP3-Owner': '2'}
        assert client.get('/jobs/' + job, headers=other).status_code == 404
        assert client.get('/jobs/' + job + '/result', headers=other).status_code == 404
        assert client.delete('/jobs/' + job, headers=other).status_code == 404
        wait(client, job)
        assert client.get('/jobs/' + job + '/result', headers=HEADERS).json()['outputs']['txt'] == 'Olá'
    assert not list(tmp_path.glob('*.media'))


def test_single_active_job_and_cancellation(tmp_path):
    entered = threading.Event()
    def slow(source, **kwargs):
        entered.set()
        while not kwargs['cancelled'](): time.sleep(.01)
        raise InterruptedError()
    with TestClient(create_app(tmp_path, TOKEN, slow)) as client:
        job = client.post('/jobs', headers=HEADERS, content=b'audio').json()['id']
        assert entered.wait(2)
        assert client.post('/jobs', headers=HEADERS, content=b'audio').status_code == 429
        assert client.delete('/jobs/' + job, headers=HEADERS).status_code == 200
        wait(client, job, ('cancelled',))
        assert client.get('/jobs/' + job + '/result', headers=HEADERS).status_code == 409
    assert not list(tmp_path.glob('*.media'))


def test_recovery_and_ttl(tmp_path):
    store = Store(tmp_path)
    with store.connect() as db:
        db.execute("INSERT INTO jobs(id,owner,model,state,created) VALUES('abc','1','tiny','running',?)", (time.time(),))
    store = Store(tmp_path)
    assert store.get('abc')['state'] == 'queued'
    store.update('abc', state='done', finished=time.time()-100)
    store.cleanup(10)
    with pytest.raises(Exception): store.get('abc')


def test_worker_error_removes_audio(tmp_path):
    def fail(*args, **kwargs): raise ValueError('bad audio')
    with TestClient(create_app(tmp_path, TOKEN, fail)) as client:
        job = client.post('/jobs', headers=HEADERS, content=b'audio').json()['id']
        assert wait(client, job, ('error',))['message'].startswith('Falha')
    assert not list(tmp_path.glob('*.media'))


def test_second_service_cannot_reset_running_jobs(tmp_path):
    with TestClient(create_app(tmp_path, TOKEN, fake)):
        with pytest.raises(Timeout): create_app(tmp_path, TOKEN, fake)


def test_missing_secret_rejected(tmp_path):
    with pytest.raises(RuntimeError): create_app(tmp_path, 'short')
