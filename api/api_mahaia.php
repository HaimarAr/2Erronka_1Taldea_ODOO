<?php
require("db_parameters.php");
header('Content-Type: application/json; charset=utf-8');

// Configuración de la conexión a MySQL
$host = "localhost:3306";
$username = "root";
$password = "1WMG2023";
$database = "5_erronka";

// Log para depuración
file_put_contents('debug.log', "Conectando a la base de datos: $database\n", FILE_APPEND);

try {
    $pdo = new PDO("mysql:host=$host;dbname=$database;charset=utf8", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    file_put_contents('debug.log', "Conexión exitosa a la base de datos\n", FILE_APPEND);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'No se pudo conectar a la base de datos: ' . $e->getMessage()]);
    exit;
}

// Verificar que la solicitud sea POST
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Método no permitido. Use POST.']);
    exit;
}

// Obtener los datos enviados desde Odoo
$input = json_decode(file_get_contents('php://input'), true);

if (!$input) {
    http_response_code(400);
    echo json_encode(['error' => 'Datos JSON inválidos']);
    exit;
}

// Campos esperados desde Odoo
$zenbakia = isset($input['zenbakia']) ? (int)$input['zenbakia'] : null;
$eserlekuak = isset($input['eserlekuak']) ? (int)$input['eserlekuak'] : null;
$habilitado = isset($input['habilitado']) ? (bool)$input['habilitado'] : null;
$terraza = isset($input['terraza']) ? (bool)$input['terraza'] : null;
$updated_at = isset($input['updated_at']) ? $input['updated_at'] : null;

// Validar campos requeridos
if (!$zenbakia || !isset($input['eserlekuak'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Faltan campos requeridos (zenbakia, eserlekuak)']);
    exit;
}

// Verificar que la tabla mahaia existe y tiene las columnas correctas
try {
    $stmt = $pdo->query("DESCRIBE mahaia");
    $columns = $stmt->fetchAll(PDO::FETCH_COLUMN);
    file_put_contents('debug.log', "Columnas de la tabla mahaia: " . implode(", ", $columns) . "\n", FILE_APPEND);

    if (!in_array('mahaila_zenbakia', $columns)) {
        http_response_code(500);
        echo json_encode(['error' => 'La columna mahaila_zenbakia no existe en la tabla mahaia']);
        exit;
    }
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Error al verificar la tabla mahaia: ' . $e->getMessage()]);
    exit;
}

// Insertar la nueva mesa en la base de datos
try {
    $query = "INSERT INTO mahaia (mahaila_zenbakia, eserlekuak, habilitado, terraza, updated_at) 
              VALUES (:mahaila_zenbakia, :eserlekuak, :habilitado, :terraza, :updated_at)";
    $stmt = $pdo->prepare($query);
    $stmt->execute([
        ':mahaila_zenbakia' => $zenbakia,
        ':eserlekuak' => $eserlekuak,
        ':habilitado' => $habilitado ? 1 : 0,
        ':terraza' => $terraza ? 1 : 0,
        ':updated_at' => $updated_at
    ]);

    http_response_code(201);
    echo json_encode(['message' => 'Mesa creada exitosamente']);
} catch (PDOException $e) {
    if (strpos($e->getMessage(), 'Duplicate entry') !== false) {
        http_response_code(409);
        echo json_encode(['error' => "El mahaila_zenbakia $zenbakia ya existe"]);
    } else {
        http_response_code(500);
        echo json_encode(['error' => 'Error al guardar la mesa: ' . $e->getMessage()]);
    }
}
?>