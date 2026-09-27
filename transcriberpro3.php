<?php
/**
 * Plugin Name: Transcriber Pro 3
 * Description: Transcrição local no Windows, com alternativa privada de processamento na VPS. Shortcode: [transcriberpro3].
 * Version: 3.0.0
 * Requires at least: 6.4
 * Requires PHP: 8.1
 * Author: Daniel Paixão
 */
if (!defined('ABSPATH')) { exit; }

function tp3_permission() {
    return current_user_can('transcribe_tp3');
}
register_activation_hook(__FILE__, function () {
    $role = get_role('administrator');
    if ($role) { $role->add_cap('transcribe_tp3'); }
});

function tp3_proxy($request) {
    if (!defined('TP3_API_TOKEN') || strlen(TP3_API_TOKEN) < 32 || !function_exists('curl_init')) {
        return new WP_Error('tp3_config', 'Alternativa no servidor não configurada.', array('status' => 503));
    }
    // Fixed loopback upstream: no URL supplied by a visitor and no public worker port.
    $params = $request->get_url_params();
    $id = isset($params['id']) ? $params['id'] : null;
    $route = '/jobs';
    if ($id) { $route .= '/' . $id; }
    if (isset($params['result'])) { $route .= '/result'; }
    $headers = array('Authorization: Bearer ' . TP3_API_TOKEN, 'X-TP3-Owner: ' . get_current_user_id());
    $method = $request->get_method();
    $handle = null;
    if ($method === 'POST') {
        $files = $request->get_file_params();
        $file = isset($files['media']) ? $files['media'] : null;
        if (!$file || $file['error'] !== UPLOAD_ERR_OK || !is_uploaded_file($file['tmp_name'])) {
            return new WP_Error('tp3_upload', 'Envio inválido. Verifique os limites do PHP/Nginx.', array('status' => 400));
        }
        $size = filesize($file['tmp_name']);
        if ($size < 1 || $size > 100 * 1024 * 1024) {
            return new WP_Error('tp3_size', 'Use um arquivo de até 100 MiB.', array('status' => 413));
        }
        $model = $request->get_param('model') ?: 'base';
        if (!in_array($model, array('tiny', 'base', 'small'), true)) {
            return new WP_Error('tp3_model', 'Modelo inválido.', array('status' => 400));
        }
        $route .= '?model=' . rawurlencode($model);
        $handle = fopen($file['tmp_name'], 'rb');
        if (!$handle) { return new WP_Error('tp3_file', 'Não foi possível ler o arquivo.', array('status' => 500)); }
        $headers[] = 'Content-Type: application/octet-stream';
        $headers[] = 'Expect:';
    }
    $curl = curl_init('http://127.0.0.1:8766' . $route);
    $options = array(
        CURLOPT_RETURNTRANSFER => true, CURLOPT_HTTPHEADER => $headers,
        CURLOPT_CONNECTTIMEOUT => 5, CURLOPT_TIMEOUT => 120,
        CURLOPT_FOLLOWLOCATION => false, CURLOPT_PROTOCOLS => CURLPROTO_HTTP,
        CURLOPT_PROXY => '',
    );
    if ($handle) {
        $options[CURLOPT_UPLOAD] = true;
        $options[CURLOPT_INFILE] = $handle;
        $options[CURLOPT_INFILESIZE] = $size;
    }
    $options[CURLOPT_CUSTOMREQUEST] = $method;
    curl_setopt_array($curl, $options);
    $body = curl_exec($curl);
    $code = curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
    curl_close($curl);
    if ($handle) { fclose($handle); }
    if ($body === false || !$code) {
        return new WP_Error('tp3_offline', 'Processamento no servidor indisponível.', array('status' => 503));
    }
    $data = json_decode($body, true);
    if (!is_array($data)) {
        return new WP_Error('tp3_response', 'Resposta inválida do servidor.', array('status' => 502));
    }
    $response = new WP_REST_Response($data, $code);
    $response->header('Cache-Control', 'no-store, private');
    return $response;
}

add_action('rest_api_init', function () {
    register_rest_route('tp3/v1', '/jobs', array(
        'methods' => 'POST', 'callback' => 'tp3_proxy', 'permission_callback' => 'tp3_permission',
    ));
    register_rest_route('tp3/v1', '/jobs/(?P<id>[a-f0-9]{32})', array(
        'methods' => array('GET', 'DELETE'), 'callback' => 'tp3_proxy', 'permission_callback' => 'tp3_permission',
    ));
    register_rest_route('tp3/v1', '/jobs/(?P<id>[a-f0-9]{32})/(?P<result>result)', array(
        'methods' => 'GET', 'callback' => 'tp3_proxy', 'permission_callback' => 'tp3_permission',
    ));
});

add_shortcode('transcriberpro3', function () {
    wp_enqueue_style('tp3-ui', plugins_url('assets/app.css', __FILE__), array(), '3.0.0');
    wp_enqueue_script('tp3-ui', plugins_url('assets/app.js', __FILE__), array(), '3.0.0', true);
    $url = defined('TP3_WINDOWS_DOWNLOAD_URL') ? esc_url(TP3_WINDOWS_DOWNLOAD_URL) : '';
    $config = array('api' => rest_url('tp3/v1/'), 'nonce' => wp_create_nonce('wp_rest'));
    ob_start(); ?>
    <section class="tp3" data-config="<?php echo esc_attr(wp_json_encode($config)); ?>">
        <h2>Transcriber Pro 3</h2>
        <h3>Transcreva no seu computador</h3>
        <p>Recomendado: abra o aplicativo Windows e escolha seu áudio ou vídeo. O arquivo permanece no seu PC, sem consumir o processamento do site.</p>
        <?php if ($url) : ?>
            <p><a class="tp3-download" href="<?php echo $url; ?>">Baixar aplicativo para Windows</a></p>
        <?php else : ?>
            <p>O administrador ainda precisa disponibilizar o pacote Windows.</p>
        <?php endif; ?>
        <ol><li>Extraia o ZIP inteiro e abra TranscriberPro3.exe.</li><li>Escolha o arquivo e o modelo. O primeiro uso baixa o modelo; os próximos reutilizam a cópia local.</li><li>Revise e salve em TXT, SRT ou VTT.</li></ol>
        <p>Modelos: <code>%LOCALAPPDATA%\TranscritorLocalPro\modelos</code>. Não é preciso instalar Python no computador do usuário.</p>
        <?php if (tp3_permission() && defined('TP3_API_TOKEN')) : ?>
        <details><summary>Preciso usar o processamento do servidor</summary>
            <p>Esta opção envia o arquivo à VPS. Áudios são apagados após o processamento; resultados ficam disponíveis por até 24 horas na configuração padrão.</p>
            <form class="tp3-form">
                <label>Áudio ou vídeo (até 100 MiB) <input type="file" name="media" accept="audio/*,video/*" required></label>
                <label>Modelo <select name="model"><option value="tiny">Tiny — mais leve</option><option value="base" selected>Base — equilibrado</option><option value="small">Small — mais lento</option></select></label>
                <label><input type="checkbox" required> Autorizo o envio deste arquivo ao servidor para transcrição.</label>
                <button type="submit">Enviar e transcrever na VPS</button>
                <button type="button" class="tp3-cancel" disabled>Cancelar</button>
            </form>
            <p class="tp3-status" role="status" aria-live="polite"></p>
            <progress class="tp3-progress" max="100" value="0"></progress>
            <div class="tp3-results"></div>
        </details>
        <?php else : ?>
            <p>A alternativa no servidor exige acesso autorizado pelo administrador.</p>
        <?php endif; ?>
    </section>
    <?php return ob_get_clean();
});
