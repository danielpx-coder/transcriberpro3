# Implantação em WordPress + Nginx

Alvo: VPS Linux x64 com systemd, WordPress existente, PHP >= 8.1 com extensão cURL e Python 3.11 no **servidor**. Não é necessário mudar o banco MySQL/MariaDB do WordPress. Use ambiente de homologação antes de ativar em produção.

## 1. Plugin e caminho local (funciona sem worker)

Na raiz do repositório:

```bash
python scripts/package-plugin.py
```

Instale `dist/transcriberpro3-wordpress.zip` em **Plugins → Adicionar plugin → Enviar plugin** e ative. Crie uma página com:

```text
[transcriberpro3]
```

Após construir e testar o aplicativo Windows, publique o ZIP e inclua em `wp-config.php`, antes de carregar WordPress:

```php
define('TP3_WINDOWS_DOWNLOAD_URL', 'https://SEU-DOMINIO/downloads/TranscriberPro3-windows-x64.zip');
```

Substitua pelo endereço real do arquivo. Não aponte para ZIP de código-fonte. Sem essa constante, a página informa que o pacote ainda não foi disponibilizado.

## 2. Worker opcional

Faça checkout da versão aprovada em `/opt/transcriberpro3`. Exemplo, ajustando a referência para o commit/release que você vai implantar:

```bash
sudo useradd --system --home /var/lib/transcriberpro3 --shell /usr/sbin/nologin transcriberpro3
sudo git clone https://github.com/danielpx-coder/transcriberpro3.git /opt/transcriberpro3
cd /opt/transcriberpro3
# git checkout REF_APROVADA
sudo python3.11 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements-server.txt
sudo install -m 600 deploy/transcriberpro3.env.example /etc/transcriberpro3.env
sudo install -m 644 deploy/transcriberpro3.service /etc/systemd/system/transcriberpro3.service
```

Gere um segredo com `openssl rand -hex 32`. Edite `/etc/transcriberpro3.env` como root e substitua o placeholder por esse segredo. No `wp-config.php`, configure o mesmo valor:

```php
define('TP3_API_TOKEN', 'COLE_AQUI_O_MESMO_SEGREDO_ALEATORIO');
```

Não coloque esse segredo no Git, JavaScript, shortcode, logs ou campo público do site. O plugin envia o segredo somente ao worker privado. Use permissão de arquivo restrita compatível com PHP-FPM para `wp-config.php`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now transcriberpro3
sudo systemctl status transcriberpro3
sudo journalctl -u transcriberpro3 -n 50 --no-pager
```

O `StateDirectory` do systemd cria `/var/lib/transcriberpro3`; o processo não deve ter escrita no código em `/opt`. Dados, pesos e fila ficam fora do webroot. Use **um único processo** e `--workers 1`; um bloqueio de arquivo recusa uma segunda instância sobre a mesma fila.

O serviço é limitado a 200% de CPU (dois núcleos equivalentes) e 4 GB RAM. Ajuste com medição real; `small` e gravações longas podem ultrapassar a memória disponível. O tamanho comprimido do upload não limita a duração nem a memória de áudio decodificado. Não libere a alternativa no servidor indiscriminadamente para contas públicas; para volume maior, adicione limite de duração, cotas por plano e supervisão de workers antes de escalar.

Downloads de modelos ocorrem no primeiro trabalho e podem demorar. Para pré-baixar `base`, execute com o mesmo usuário e diretórios do serviço após ele criar a pasta:

```bash
sudo -u transcriberpro3 env TP3_DATA_DIR=/var/lib/transcriberpro3 HF_HOME=/var/lib/transcriberpro3/huggingface /opt/transcriberpro3/.venv/bin/python -c 'from tp3.models import ensure_model; print(ensure_model("base"))'
```

Execute a partir de `/opt/transcriberpro3`. Cache do servidor e cache Windows são independentes.

## 3. Permissões WordPress

Por padrão, apenas administradores recebem `transcribe_tp3` ao ativar o plugin. Para autorizar um usuário específico, use WP-CLI com o nome real da conta:

```bash
wp user add-cap NOME_DO_USUARIO transcribe_tp3
```

Para revogar:

```bash
wp user remove-cap NOME_DO_USUARIO transcribe_tp3
```

Não conceda a capacidade ao papel `subscriber` em um site de cadastro aberto sem implementar cotas adicionais. A API valida a capacidade, usa a autenticação de sessão/nonce REST do WordPress e atribui o proprietário a partir da sessão. O navegador não escolhe o ID do usuário no worker.

## 4. Nginx, PHP-FPM e cache

Mescle `deploy/nginx-snippet.conf` no vhost existente. Configure PHP-FPM com `upload_max_filesize=100M`, `post_max_size=110M`, `max_execution_time=180`. O corpo passa em streaming do temporário PHP para o worker; Whisper roda fora do PHP-FPM.

- Nginx: `client_max_body_size 110m`.
- Preserve o `try_files` e a configuração PHP existentes.
- Desative cache de página na página do shortcode e cache para `/wp-json/tp3/`, incluindo instalações que usam `?rest_route=`. Nonces/sessões não devem ser compartilhados em cache público.
- Use HTTPS no site; **não abra 8766** no firewall, nem faça proxy público dessa porta.
- O worker e o PHP devem estar no mesmo namespace de rede. Se usar containers separados, este exemplo de loopback precisa ser adaptado e auditado.
- Verifique temporários de upload Nginx/PHP, permissões e espaço em disco. Esses temporários também dependem da política de limpeza do servidor.

```bash
sudo nginx -t
# Somente depois do teste acima:
sudo systemctl reload nginx
# Recarregue também a unidade PHP-FPM específica da sua instalação.
```

## 5. Operação e privacidade

Fila SQLite: `/var/lib/transcriberpro3/jobs.db`. Resultados só podem ser consultados pelo dono através da sessão WordPress. Áudios enviados não entram na biblioteca de mídia do site. Após conclusão/erro/cancelamento, o worker remove sua cópia; resultados ficam na fila por 24h, configurável em `TP3_RETENTION_SECONDS`.

A limpeza ocorre enquanto o serviço está rodando. Fila em execução é preservada em uma parada; ao reiniciar, o trabalho recomeça do início. O usuário pode recarregar a mesma aba do navegador para retomar o acompanhamento pelo `sessionStorage`; não há uma lista web de histórico nesta base. Backups, snapshots e logs têm retenção independente: configure-os de acordo com sua operação. A exclusão lógica não equivale à sobrescrita física de discos/backups.

Atualizações: pare o serviço, atualize o checkout e dependências, confira os testes e reinicie; preserve `/var/lib/transcriberpro3`. Para desativar o fallback, remova `TP3_API_TOKEN` do WordPress e pare o serviço. O caminho local continua disponível.

## Contrato interno

Todos os endpoints exigem `Authorization: Bearer SEGREDO` e `X-TP3-Owner: ID_WORDPRESS`. Somente o plugin constrói esses cabeçalhos.

| Método | Caminho | Entrada / saída |
|---|---|---|
| GET | `/health` | Estado autenticado |
| POST | `/jobs?model=base` | Corpo binário bruto → `202 {id,state}` |
| GET | `/jobs/{id}` | Estado, progresso e mensagem |
| GET | `/jobs/{id}/result` | Segmentos e saídas TXT/SRT/VTT |
| DELETE | `/jobs/{id}` | Solicitação de cancelamento |

O endpoint público WordPress equivalente para criar é `POST /wp-json/tp3/v1/jobs`, com formulário multipart `media` + `model` e cabeçalho `X-WP-Nonce`. O plugin valida o upload e transmite o arquivo binário ao worker. Campos de rota são extraídos da URL registrada, não de parâmetros enviados pelo visitante.
