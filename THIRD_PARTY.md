# Dependências e redistribuição

O motor é faster-whisper (MIT), com CTranslate2 (MIT), PyAV (BSD) e bibliotecas FFmpeg incluídas nas wheels de PyAV. A interface usa Python/Tk; PyInstaller inclui o interpretador e as dependências no pacote Windows. PyInstaller tem exceção de licença para aplicações empacotadas. Hugging Face Hub fornece o transporte de modelos.

Os pesos vêm de `Systran/faster-whisper-{tiny,base,small,medium}` e `mobiuslabsgmbh/faster-whisper-large-v3-turbo`, conversões de Whisper, com revisões fixadas em `tp3/models.py`. São modelos CTranslate2, não arquivos `.pt`; não renomeie pesos PyTorch para `model.bin`.

O build copia metadados e arquivos de licença das distribuições instaladas para `licenses/`. Antes de uma distribuição pública, revise também as licenças das DLLs efetivamente incluídas (FFmpeg e componentes transitivos), as model cards das revisões usadas e as obrigações de redistribuição. Não há DLL CUDA de terceiros incorporada por este projeto.

Fontes técnicas consultadas:
- https://github.com/SYSTRAN/faster-whisper
- https://opennmt.net/CTranslate2/installation.html
- https://pyinstaller.org/en/stable/operating-mode.html
- https://huggingface.co/docs/huggingface_hub/package_reference/file_download
