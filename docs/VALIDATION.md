# Validação — 27/09/2026 UTC (solicitação de 26/09 no Brasil)

Este relatório separa testes executados de verificações que dependem do ambiente de destino. Código implementado e testes com substitutos não são prova de funcionamento integral no Windows ou no WordPress de produção.

## Executado neste ambiente Linux

| Verificação | Resultado / alcance |
|---|---|
| Checkout do repositório | `main` em `883b3a8df4f72e0d41ffe953bc4ead2b3d1854c0`; somente `transcriberpro3.php`, 1 byte |
| Instalação de `requirements-dev.txt` | Concluída em venv Python 3.12.14 Linux x64 |
| `pip check` | Nenhuma dependência quebrada |
| `python -m pytest -q` | 15 testes aprovados; 1 aviso de depreciação transitivo do Starlette/AnyIO |
| Compilação sintática Python | `compileall` aprovado para motor, desktop, servidor e scripts |
| JavaScript | `node --check assets/app.js` aprovado |
| `python -m desktop.main --self-test` | Importação real de faster-whisper, CTranslate2 e PyAV; exportação básica aprovada, sem abrir GUI |
| Metadados dos modelos | Repositórios/revisões consultados no Hugging Face; metadados/hash do tiny obtidos pela API real |
| Cache e integridade | Testes com arquivos pequenos controlados: cache sem rede, reparo seletivo, rejeição de download corrompido, checksum Git e manifesto sem fuga de diretório |
| Alternativa GPU → CPU | Teste com substituto simulando erro CUDA após segmento; não é teste em GPU física |
| API/worker | TestClient ASGI com motor substituto: fluxo upload → fila → resultado, usuário diferente recusado, limites, cancelamento, remoção do áudio e exclusão por prazo |
| Recuperação de fila | Estado `running` recolocado em `queued`; não verifica recuperação de timestamps |
| PHP local | PHP CLI indisponível; instalação pelo gerenciador do ambiente bloqueada por permissões. Lint e smoke test previstos no job Linux do Actions |

### Inferência real em CPU — aprovada

O modelo `tiny` foi baixado do Hugging Face (~75 MB de pesos), verificado com os hashes do upstream e carregado pelo faster-whisper/CTranslate2 em CPU. Um WAV de 1 segundo de silêncio foi processado e gerou as três saídas, sem segmentos de fala. Em seguida, `python -m scripts.smoke-real --cache /tmp/tp3-real-models` repetiu a inferência e executou novamente com conexões de rede bloqueadas no processo: ambas concluíram e produziram saídas iguais. Isso confirma execução real e reuso offline neste Linux; **não comprova qualidade de reconhecimento de voz, funcionamento da GUI ou compatibilidade Windows**.

Também foi executado o fluxo ASGI completo com o motor real: upload do WAV → fila SQLite → inferência CPU com tiny → consulta das três saídas. A cópia do áudio enviado foi removida após conclusão. Esse teste não inclui PHP, WordPress, Nginx ou uma conexão HTTP externa.

## Automação adicionada

`.github/workflows/ci.yml` executa testes Python, lint PHP, teste de rotas com funções WordPress substituídas, checagem JavaScript e empacotamento do plugin. O job Windows constrói via PyInstaller e executa `--self-test` do executável empacotado antes de produzir ZIP.

O smoke test do executável verifica importações/bibliotecas, exportação e inicialização de uma janela Tk oculta no Windows, sem download de modelo nem interação com a GUI. A presença do workflow não significa que uma execução passou: confira a execução específica do commit no Actions.

## Homologação pendente no Windows real

- [ ] Windows 10 x64 limpo, sem Python, pip ou FFmpeg: extrair ZIP e abrir interface.
- [ ] Repetir em Windows 11 x64 e conferir dependência de runtime Visual C++.
- [ ] Arquivo de voz PT-BR real em WAV, MP3, M4A e vídeo MP4; caminhos com espaços e acentos.
- [ ] Baixar tiny/base e confirmar o caminho exato em `%LOCALAPPDATA%`.
- [ ] Desligar a internet e repetir a transcrição, comprovando reuso sem download.
- [ ] Interromper download, reiniciar e verificar reparação; testar falta de disco/permissão.
- [ ] Conferir timestamps, acentos, revisão e abertura das exportações em editor/player externo.
- [ ] GPU NVIDIA compatível com CUDA/cuDNN; GPU sem DLLs; computador só com CPU.
- [ ] Cancelar durante download/inferência, verificar feedback e capacidade de iniciar novo trabalho.
- [ ] Medir consumo em PC antigo e revisar modelos permitidos/recomendados.
- [ ] Avaliar antivírus/SmartScreen, licenças de DLLs e assinatura de distribuição.

## Homologação pendente na VPS/WordPress real

- [ ] Instalar ZIP pelo painel, ativar e renderizar shortcode no tema existente e em tela móvel.
- [ ] Sessão/nonce REST real: anônimo bloqueado; usuário sem capacidade bloqueado; conta autorizada aceita.
- [ ] Dois usuários reais: um não acessa nem cancela os trabalhos do outro.
- [ ] Upload multipart via navegador → temporário PHP → stream cURL → API privada → Whisper real → download TXT/SRT/VTT.
- [ ] Worker sem acesso público, serviço sem root, código somente leitura, token correto e cache REST desativado.
- [ ] Limites PHP/Nginx, timeouts, arquivo inválido, upload interrompido, saturação da fila, pouco disco/RAM.
- [ ] Reiniciar/matar worker durante trabalho e confirmar reexecução única a partir do início.
- [ ] Conferir retenção, limpeza de temporários, logs e backups após 24h.
- [ ] Medir memória e CPU com gravações longas antes de liberar modelos/usuários adicionais.

Não foram implantadas alterações na VPS nem instalados componentes no computador do usuário.

## Resultado confirmado do GitHub Actions

Execução [36288661448](https://github.com/danielpx-coder/transcriberpro3/actions/runs/36288661448), código do commit `83405723976ecd8e357ce3bda1029a22b7050f96`: **jobs Linux e Windows aprovados**.

- Linux/Python 3.11: 15 testes, lint PHP, contrato de rotas/capacidade com substitutos WordPress, checagem JS e ZIP do plugin aprovados.
- Windows Server 2022/Python 3.11: PyInstaller produziu o ZIP; o executável passou em imports de dependências, exportação e abertura/fechamento de Tk oculto. Não houve teste de inferência Windows nem interação humana com a GUI.
- Artefatos: `TranscriberPro3-windows-x64` (aproximadamente 97 MiB) e `wordpress-plugin`, disponíveis na execução acima. O download do artefato contém o ZIP interno: extraia o arquivo do Actions antes de usar o ZIP do plugin no WordPress.
- SHA-256 do **ZIP Windows interno**: `B945E4A30FE088AC49D56F0FF31FB4F4F9686EDF330D7930FB163D5055DABFF7`.
- Artefatos do Actions não são uma Release permanente. Nesta execução, a expiração informada é 26/12/2026; publique uma cópia homologada para distribuição aos usuários.

A falha inicial do CI foi a busca padrão por `requirements.txt`, incompatível com os arquivos separados do projeto; `cache-dependency-path: requirements-*.txt` corrigiu a configuração. A execução citada acima passou após a correção. Este registro posterior altera apenas documentação, preservando o código validado.
