"""Private single-worker service. WordPress is the only public entry point."""
import asyncio
from contextlib import asynccontextmanager, contextmanager
import hmac
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from tp3.engine import transcribe

LOG = logging.getLogger('tp3')


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, model TEXT NOT NULL,
                state TEXT NOT NULL, progress INTEGER DEFAULT 0, message TEXT DEFAULT '',
                result TEXT, cancel INTEGER DEFAULT 0, created REAL NOT NULL, finished REAL)''')
            # Interrupted work is retried from the beginning, not from a saved timestamp.
            db.execute("UPDATE jobs SET state='queued', progress=0, message='Retomado após reinício' WHERE state='running'")
            # An interrupted upload was never committed to the queue.
            for path in self.root.glob('*.media'):
                if not db.execute('SELECT 1 FROM jobs WHERE id=?', (path.stem,)).fetchone():
                    path.unlink(missing_ok=True)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / 'jobs.db', timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, job_id, owner=None):
        with self.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row or (owner is not None and row['owner'] != owner):
            raise HTTPException(404, 'Trabalho não encontrado')
        return dict(row)

    def update(self, job_id, **values):
        allowed = {'state', 'progress', 'message', 'result', 'cancel', 'finished'}
        if not set(values).issubset(allowed):
            raise ValueError('Coluna inválida')
        with self.connect() as db:
            db.execute('UPDATE jobs SET ' + ','.join(f'{key}=?' for key in values) + ' WHERE id=?',
                       [*values.values(), job_id])

    def cleanup(self, ttl):
        with self.connect() as db:
            old = db.execute('SELECT id FROM jobs WHERE finished < ?', (time.time() - ttl,)).fetchall()
            for row in old:
                (self.root / (row['id'] + '.media')).unlink(missing_ok=True)
                db.execute('DELETE FROM jobs WHERE id=?', (row['id'],))


def create_app(root=None, token=None, runner=transcribe, max_bytes=None, ttl=None):
    secret = token or os.environ.get('TP3_API_TOKEN', '')
    if len(secret) < 32 or secret.startswith('REPLACE_'):
        raise RuntimeError('Defina TP3_API_TOKEN com pelo menos 32 caracteres aleatórios.')
    from filelock import FileLock
    storage_root = Path(root or os.environ.get('TP3_DATA_DIR', '/var/lib/transcriberpro3'))
    storage_root.mkdir(parents=True, exist_ok=True)
    process_lock = FileLock(str(storage_root / '.service.lock'), timeout=0)
    process_lock.acquire()
    storage = Store(storage_root)
    limit = max_bytes or int(os.environ.get('TP3_MAX_BYTES', 100 * 1024 * 1024))
    retention = ttl or int(os.environ.get('TP3_RETENTION_SECONDS', 86400))
    shutting_down = threading.Event()
    upload_lock = asyncio.Lock()

    def worker():
        while not shutting_down.is_set():
            storage.cleanup(retention)
            with storage.connect() as db:
                row = db.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
                if row:
                    db.execute("UPDATE jobs SET state='running' WHERE id=?", (row['id'],))
            if not row:
                shutting_down.wait(.25)
                continue
            job = storage.get(row['id'])
            source = storage.root / (job['id'] + '.media')
            try:
                if job['cancel']:
                    raise InterruptedError()
                result = runner(source, model=job['model'], device='cpu', root=storage.root / 'modelos',
                                report=lambda s: storage.update(job['id'], message=s),
                                progress=lambda p: storage.update(job['id'], progress=p),
                                cancelled=lambda: shutting_down.is_set() or bool(storage.get(job['id'])['cancel']))
                if storage.get(job['id'])['cancel']:
                    raise InterruptedError()
                storage.update(job['id'], state='done', progress=100, result=json.dumps(result), finished=time.time())
            except InterruptedError:
                if shutting_down.is_set() and not storage.get(job['id'])['cancel']:
                    storage.update(job['id'], state='queued', progress=0)
                else:
                    storage.update(job['id'], state='cancelled', finished=time.time())
            except Exception:
                LOG.exception('Falha no trabalho %s', job['id'])
                storage.update(job['id'], state='error', message='Falha ao transcrever. Consulte o administrador.', finished=time.time())
            finally:
                if storage.get(job['id'])['state'] != 'queued':
                    source.unlink(missing_ok=True)

    @asynccontextmanager
    async def lifespan(app):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        yield
        shutting_down.set()
        await asyncio.to_thread(thread.join, 10)
        if not thread.is_alive():
            process_lock.release()

    app = FastAPI(title='TP3 private worker', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = storage

    def identity(authorization: str = Header(default=''), x_tp3_owner: str = Header(default='')):
        if not hmac.compare_digest(authorization.encode('utf-8'), ('Bearer ' + secret).encode('utf-8')):
            raise HTTPException(401, 'Não autorizado')
        if not re.fullmatch(r'[1-9][0-9]{0,19}', x_tp3_owner):
            raise HTTPException(400, 'Usuário inválido')
        return x_tp3_owner

    @app.get('/health')
    def health(owner=Depends(identity)):
        return {'ok': True}

    @app.post('/jobs', status_code=202)
    async def create(request: Request, model: str = 'base', owner=Depends(identity)):
        # Server deliberately allows only small models to bound VPS usage.
        if model not in ('tiny', 'base', 'small'):
            raise HTTPException(400, 'Modelo não permitido no servidor')
        try:
            length = int(request.headers.get('content-length', '0'))
        except ValueError:
            raise HTTPException(400, 'Tamanho inválido')
        if length > limit or length < 0:
            raise HTTPException(413, 'Arquivo grande demais')
        async with upload_lock:
            with storage.connect() as db:
                active = db.execute("SELECT owner FROM jobs WHERE state IN ('queued','running')").fetchall()
                recent = db.execute('SELECT COUNT(*) FROM jobs WHERE owner=? AND created>?', (owner, time.time()-3600)).fetchone()[0]
            if len(active) >= 8 or any(r['owner'] == owner for r in active) or recent >= 10:
                raise HTTPException(429, 'Limite de fila ou de trabalhos por hora atingido')
            job_id = uuid.uuid4().hex
            source = storage.root / (job_id + '.media')
            total = 0
            try:
                with source.open('xb') as stream:
                    async for chunk in request.stream():
                        total += len(chunk)
                        if total > limit:
                            raise HTTPException(413, 'Arquivo grande demais')
                        stream.write(chunk)
                if not total:
                    raise HTTPException(400, 'Arquivo vazio')
                with storage.connect() as db:
                    db.execute('INSERT INTO jobs(id,owner,model,state,created) VALUES(?,?,?,?,?)',
                               (job_id, owner, model, 'queued', time.time()))
            except BaseException:
                source.unlink(missing_ok=True)
                raise
        return {'id': job_id, 'state': 'queued'}

    @app.get('/jobs/{job_id}')
    def status(job_id: str, owner=Depends(identity)):
        job = storage.get(job_id, owner)
        return {key: job[key] for key in ('id', 'state', 'progress', 'message')}

    @app.get('/jobs/{job_id}/result')
    def result(job_id: str, owner=Depends(identity)):
        job = storage.get(job_id, owner)
        if job['state'] != 'done':
            raise HTTPException(409, 'Resultado indisponível')
        return json.loads(job['result'])

    @app.delete('/jobs/{job_id}')
    def cancel(job_id: str, owner=Depends(identity)):
        storage.get(job_id, owner)
        # One transaction prevents a queued/running race with the worker.
        with storage.connect() as db:
            db.execute('UPDATE jobs SET cancel=1 WHERE id=?', (job_id,))
            db.execute("UPDATE jobs SET state='cancelled', finished=? WHERE id=? AND state='queued'", (time.time(), job_id))
        if storage.get(job_id)['state'] == 'cancelled':
            (storage.root / (job_id + '.media')).unlink(missing_ok=True)
        return {'ok': True}

    return app
