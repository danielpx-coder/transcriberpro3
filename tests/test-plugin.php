<?php
// Contract smoke test with WP stubs; not an end-to-end WordPress test.
define('ABSPATH', __DIR__);
$routes = array();
function register_activation_hook($file, $callback) {}
function add_action($name, $callback) { if ($name === 'rest_api_init') { $callback(); } }
function add_shortcode($name, $callback) {}
function register_rest_route($namespace, $route, $args) { global $routes; $routes[$route] = $args; }
function current_user_can($cap) { return false; }
require __DIR__ . '/../transcriberpro3.php';
if (count($routes) !== 3 || tp3_permission() !== false) { exit(1); }
foreach ($routes as $route) {
    if ($route['permission_callback'] !== 'tp3_permission') { exit(2); }
}
echo "PHP routes/capability smoke test OK (stubbed WP).\n";
