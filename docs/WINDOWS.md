# Windows 10/11 x64

## Usuário final

Use o ZIP **compilado no Windows**, disponibilizado pelo administrador. Um ZIP do código-fonte do GitHub não é o aplicativo portátil.

1. Extraia a pasta `TranscriberPro3` inteira em uma pasta gravável (por exemplo, Documentos). Mantenha `_internal` ao lado de `TranscriberPro3.exe`.
2. Execute `TranscriberPro3.exe`, escolha seu arquivo e comece com modelo `tiny` ou `base`, especialmente em PC antigo.
3. Tenha internet no primeiro uso do modelo e espaço livre para os pesos. Arquivos grandes podem exigir vários GB entre download temporário, modelo, programa e memória de trabalho.
4. Após o download, transcrições com esse modelo podem funcionar sem internet. O programa verifica os arquivos antes de reutilizá-los.
5. Revise as abas e use **Salvar aba** para cada formato. Para recuperar resultados completos, use **Abrir histórico**.

Modelos: `%LOCALAPPDATA%\TranscritorLocalPro\modelos`.
Histórico: `%LOCALAPPDATA%\TranscritorLocalPro\historico`.
Remover/atualizar a pasta do aplicativo não remove essas pastas. Apague manualmente um modelo para liberar espaço; no próximo uso será baixado novamente.

Os pesos são conversões CTranslate2 (`model.bin` e arquivos auxiliares), não `.pt`. O modelo `large-v3-turbo` aparece com esse nome no aplicativo; não copie `large-v3-turbo.pt` para essa pasta.

## CPU e GPU

`auto` tenta GPU NVIDIA quando detectada. Erros de inicialização ou execução CUDA tratados pelo motor reiniciam a transcrição na CPU, sem duplicar segmentos. `cpu` evita CUDA; `cuda` solicita GPU com a mesma alternativa por CPU. GPU Intel/AMD não está implementada.

O pacote base não traz CUDA/cuDNN; CPU não depende deles. Para GPU, a combinação CTranslate2 4.6 exige bibliotecas CUDA 12/cuBLAS e cuDNN 9 compatíveis, além do driver NVIDIA. Disponibilize as DLLs conforme a documentação oficial do faster-whisper/CTranslate2. A simples existência de uma GPU não garante compatibilidade. Dependendo da máquina, pode ser necessário o Microsoft Visual C++ Redistributable x64.

Arquitetura alvo: x64. Windows ARM, 32 bits, CPUs antigas sem instruções exigidas pelas bibliotecas e máquinas sem memória suficiente precisam de avaliação específica. Não há garantia de funcionamento nessas máquinas sem teste real.

## Construção pelo desenvolvedor

Em Windows x64, instale Python 3.11 x64 oficial com Tk e launcher `py`. Na raiz do repositório:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

O script cria ambiente isolado `.venv-build`, instala dependências fixadas diretamente, executa PyInstaller em modo pasta, copia documentação/licenças, roda smoke test do executável e produz `dist\TranscriberPro3-windows-x64.zip`. O interpretador, Tk e bibliotecas nativas são incluídos. Não copie um executável gerado no Linux para Windows: PyInstaller precisa construir no SO de destino.

Alternativa: execute o workflow **Tests and Windows package** do GitHub Actions. O runner `windows-2022` constrói o pacote; baixe o artefato da execução aprovada. Os artefatos do Actions expiram e exigem acesso adequado ao GitHub; para distribuição aos visitantes, publique o ZIP em uma Release ou download próprio e defina `TP3_WINDOWS_DOWNLOAD_URL`.

Antes de publicar, faça o checklist de `VALIDATION.md` em Windows 10 e 11 limpos, sem Python. Teste abertura da GUI, download inicial, execução offline, codecs e caminhos com acentos. Considere assinar o executável com certificado Authenticode do distribuidor; esta base não inclui certificado ou assinatura.

## Problemas comuns

- Falha ao baixar: confira internet, proxy corporativo, acesso a Hugging Face/CDN, espaço e permissões. Nenhum modelo é servido pela VPS do site.
- Modelo em uso: outra instância segura o bloqueio da pasta. Aguarde ou feche a outra transcrição.
- CPU lenta: experimente `tiny`/`base`. Modelos maiores melhoram qualidade em algumas gravações, mas custam memória e tempo.
- Cancelar parece demorar: o pedido é aplicado no próximo segmento ou após o arquivo de download atual.
- O histórico existe, mas sua revisão sumiu: revisões são salvas pelo botão de exportação; o histórico automático contém o resultado original.
