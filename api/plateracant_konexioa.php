<?php
require("db_parameters.php");
header('Content-Type: application/json; charset=utf-8');

// Desactiva la salida de errores para evitar que se añadan mensajes no deseados al JSON
ini_set('display_errors', 0);
error_reporting(0);

$conn->set_charset("utf8");

$response = [];
$plateracant = [];

try {
    // Consulta para obtener todos los registros de la vista
    $sql = "SELECT plato_id, plato_nombre, cantidad_pedidos FROM 5_erronka.view_plateracant ORDER BY cantidad_pedidos DESC";
    $result = $conn->query($sql);

    if ($result && $result->num_rows > 0) {
        while ($row = $result->fetch_assoc()) {
            $plateracant[] = $row;
        }
        $response = [
            'status_code' => 200,
            'plateracant' => $plateracant
        ];
    } else {
        $response = [
            'status_code' => 200,
            'plateracant' => []
        ];
    }
} catch (Exception $e) {
    $response = [
        'status_code' => 500,
        'mezua' => 'Errorea datu-basean: ' . $e->getMessage()
    ];
}

$conn->close();
echo json_encode($response, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
exit();
?>