import gc
from .models import ensure_model
from .formats import exports


def transcribe(source, model='base', device='auto', root=None,
               report=lambda message: None, progress=lambda percent: None,
               cancelled=lambda: False):
    if device not in ('auto', 'cpu', 'cuda'):
        raise ValueError('Dispositivo inválido')
    path = ensure_model(model, root, report, cancelled)
    if cancelled():
        raise InterruptedError('Cancelado.')
    import ctranslate2
    from faster_whisper import WhisperModel
    try:
        cuda = device != 'cpu' and ctranslate2.get_cuda_device_count() > 0
    except RuntimeError:
        cuda = False
    devices = ['cuda', 'cpu'] if cuda else ['cpu']
    for selected in devices:
        engine = None
        try:
            report(f'Transcrevendo com {selected.upper()}…')
            engine = WhisperModel(str(path), device=selected,
                                  compute_type='float16' if selected == 'cuda' else 'int8',
                                  cpu_threads=4, local_files_only=True)
            stream, info = engine.transcribe(str(source), language='pt', beam_size=5,
                                             vad_filter=False)
            segments = []
            for segment in stream:
                if cancelled():
                    raise InterruptedError('Cancelado.')
                segments.append({'start': segment.start, 'end': segment.end, 'text': segment.text})
                progress(min(99, int(segment.end / max(info.duration, 1) * 100)))
            if cancelled():
                raise InterruptedError('Cancelado.')
            progress(100)
            return {'segments': segments, 'outputs': exports(segments), 'device': selected,
                    'model': model, 'language': info.language}
        except InterruptedError:
            raise
        except (RuntimeError, OSError) as exc:
            if selected != 'cuda':
                raise
            report(f'GPU indisponível; reiniciando na CPU. ({type(exc).__name__})')
        finally:
            del engine
            gc.collect()
    raise RuntimeError('Nenhum dispositivo disponível')
