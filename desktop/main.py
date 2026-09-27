"""Portable native UI. No listening port or automatic upload to a server."""
import json
import os
import queue
import sys
import threading
import uuid
from pathlib import Path
from tp3.engine import transcribe
from tp3.models import CATALOG, data_root, atomic_json


def main():
    # PyInstaller --windowed has no console streams. Download progress libraries
    # still write to stderr, so supply a sink instead of leaving it as None.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')
    if '--self-test' in sys.argv:
        import av
        import ctranslate2
        from faster_whisper import WhisperModel
        from tp3.formats import exports
        assert 'WEBVTT' in exports([])['vtt']
        if os.name == 'nt':
            import tkinter as tk
            window = tk.Tk()
            window.withdraw()
            window.update_idletasks()
            window.destroy()
        print('Imports, export and Windows Tk initialization OK; inference not tested.')
        return
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root = tk.Tk()
    root.title('Transcriber Pro 3 — processamento no seu computador')
    root.geometry('900x670')
    events = queue.Queue()
    stop = threading.Event()
    state = {'busy': False, 'result': None}
    history = data_root() / 'historico'
    history.mkdir(parents=True, exist_ok=True)
    container = ttk.Frame(root, padding=16)
    container.pack(fill='both', expand=True)
    ttk.Label(container, text='Seu áudio fica neste computador. Idioma: português.', font=('', 12)).pack(anchor='w')
    file_var = tk.StringVar()
    row = ttk.Frame(container)
    row.pack(fill='x', pady=10)
    ttk.Entry(row, textvariable=file_var).pack(side='left', fill='x', expand=True)
    ttk.Button(row, text='Escolher áudio/vídeo', command=lambda: file_var.set(filedialog.askopenfilename() or file_var.get())).pack(side='right')
    options = ttk.Frame(container)
    options.pack(fill='x')
    model = tk.StringVar(value='base')
    device = tk.StringVar(value='auto')
    ttk.Label(options, text='Modelo:').pack(side='left')
    ttk.Combobox(options, values=list(CATALOG), textvariable=model, state='readonly', width=20).pack(side='left', padx=8)
    ttk.Label(options, text='Processamento:').pack(side='left')
    ttk.Combobox(options, values=['auto', 'cpu', 'cuda'], textvariable=device, state='readonly', width=10).pack(side='left', padx=8)
    status = tk.StringVar(value=f'Modelos permanentes: {data_root() / "modelos"}')
    ttk.Label(container, textvariable=status, wraplength=850).pack(anchor='w', pady=10)
    bar = ttk.Progressbar(container, maximum=100)
    bar.pack(fill='x')
    tabs = ttk.Notebook(container)
    tabs.pack(fill='both', expand=True, pady=10)
    editors = {}
    for fmt in ('txt', 'srt', 'vtt'):
        editor = tk.Text(tabs, wrap='word', undo=True)
        tabs.add(editor, text=fmt.upper())
        editors[fmt] = editor
    ttk.Label(container, text='Revisão: cada aba é independente. Salve cada formato revisado separadamente.').pack(anchor='w')

    def populate(result):
        state['result'] = result
        for fmt, editor in editors.items():
            editor.delete('1.0', 'end')
            editor.insert('1.0', result['outputs'][fmt])

    def work(source, model_name, target):
        try:
            result = transcribe(source, model_name, target,
                                report=lambda s: events.put(('status', s)),
                                progress=lambda p: events.put(('progress', p)), cancelled=stop.is_set)
            result['source_name'] = Path(source).name
            atomic_json(history / f'{uuid.uuid4().hex}.json', result)
            events.put(('result', result))
        except Exception as exc:
            events.put(('error', str(exc)))
        finally:
            events.put(('done', None))

    def start():
        if state['busy']:
            return
        source = file_var.get()
        if not Path(source).is_file():
            messagebox.showerror('Arquivo', 'Selecione um arquivo existente.')
            return
        state['busy'] = True
        start_button.config(state='disabled')
        bar['value'] = 0
        stop.clear()
        threading.Thread(target=work, args=(source, model.get(), device.get()), daemon=True).start()

    def save():
        fmt = ('txt', 'srt', 'vtt')[tabs.index(tabs.select())]
        path = filedialog.asksaveasfilename(defaultextension='.' + fmt, filetypes=[(fmt.upper(), '*.' + fmt)])
        if path:
            try:
                Path(path).write_text(editors[fmt].get('1.0', 'end-1c'), encoding='utf-8')
            except OSError as exc:
                messagebox.showerror('Salvar', str(exc))

    def load():
        path = filedialog.askopenfilename(initialdir=history, filetypes=[('Histórico', '*.json')])
        if path:
            try:
                populate(json.loads(Path(path).read_text(encoding='utf-8')))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                messagebox.showerror('Histórico', str(exc))

    def cancel():
        stop.set()
        status.set('Cancelamento solicitado; aguardando fim do segmento ou download atual…')

    buttons = ttk.Frame(container)
    buttons.pack(fill='x', pady=8)
    start_button = ttk.Button(buttons, text='Transcrever neste PC', command=start)
    start_button.pack(side='left')
    ttk.Button(buttons, text='Cancelar', command=cancel).pack(side='left', padx=8)
    ttk.Button(buttons, text='Salvar aba', command=save).pack(side='left')
    ttk.Button(buttons, text='Abrir histórico', command=load).pack(side='right')

    def poll():
        try:
            while True:
                kind, payload = events.get_nowait()
                if kind == 'status': status.set(payload)
                elif kind == 'progress': bar['value'] = payload
                elif kind == 'result':
                    populate(payload)
                    status.set(f'Concluído com {payload["device"].upper()}. Resultado salvo no histórico.')
                elif kind == 'error': status.set('Interrompido: ' + payload)
                elif kind == 'done':
                    state['busy'] = False
                    start_button.config(state='normal')
        except queue.Empty:
            pass
        root.after(150, poll)

    def close():
        if state['busy']:
            cancel()
            messagebox.showinfo('Aguarde', 'Cancele e aguarde a operação terminar antes de fechar.')
        else:
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    poll()
    root.mainloop()


if __name__ == '__main__':
    main()
