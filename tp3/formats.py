"""UTF-8 exports with integer millisecond rounding and valid cue boundaries."""
import math


def timestamp(seconds, separator=','):
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('Tempo inválido')
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    secs, ms = divmod(ms, 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d}{separator}{ms:03d}'


def exports(segments):
    cues = []
    text = []
    for seg in segments:
        line = ' '.join(str(seg['text']).split())
        if not line:
            continue
        start, end = float(seg['start']), float(seg['end'])
        if end < start:
            raise ValueError('Intervalo inválido')
        text.append(line)
        # Prevent a transcript token from becoming cue timing syntax.
        line = line.replace('-->', '→')
        cues.append((start, max(end, start + .001), line))
    srt, vtt = [], ['WEBVTT\n']
    for n, (start, end, line) in enumerate(cues, 1):
        srt.append(f'{n}\n{timestamp(start)} --> {timestamp(end)}\n{line}\n')
        vtt.append(f'{timestamp(start, ".")} --> {timestamp(end, ".")}\n{line}\n')
    return {'txt': '\n'.join(text) + '\n', 'srt': '\n'.join(srt), 'vtt': '\n'.join(vtt)}
