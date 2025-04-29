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

// Manejar solicitud GET: Obtener todos los trabajadores
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    try {
        $stmt = $pdo->query("SELECT * FROM langilea WHERE deleted_at IS NULL");
        $langileak = $stmt->fetchAll(PDO::FETCH_ASSOC);

        $response = [
            'status_code' => 200,
            'mezua' => 'Datos obtenidos correctamente',
            'langileak' => []
        ];

        foreach ($langileak as $langilea) {
            $response['langileak'][] = [
                'id' => (int)$langilea['id'],
                'izena' => $langilea['izena'],
                'abizena' => $langilea['abizena'],
                'email' => $langilea['email'],
                'nivel_Permisos' => isset($langilea['nivel_Permisos']) ? (int)$langilea['nivel_Permisos'] : 0,
                'txat_permiso' => isset($langilea['txat_permiso']) ? (bool)$langilea['txat_permiso'] : true,
                'created_at' => $langilea['created_at'],
                'updated_at' => $langilea['updated_at'],
                'deleted_at' => $langilea['deleted_at']
            ];
        }

        echo json_encode($response);
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Error al obtener los datos: ' . $e->getMessage()]);
    }
    exit;
}

// Manejar solicitud POST: Crear o actualizar un trabajador
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
$worker_id = isset($input['worker_id']) ? (int)$input['worker_id'] : null;
$izena = isset($input['izena']) ? $input['izena'] : null;
$abizena = isset($input['abizena']) ? $input['abizena'] : null;
$pasahitza = isset($input['pasahitza']) ? $input['pasahitza'] : null;
$email = isset($input['email']) ? $input['email'] : null;
$nivel_Permisos = isset($input['nivel_Permisos']) ? (int)$input['nivel_Permisos'] : null;
$txat_permiso = isset($input['txat_permiso']) ? (bool)$input['txat_permiso'] : null;
$created_at = isset($input['created_at']) ? $input['created_at'] : null;
$updated_at = isset($input['updated_at']) ? $input['updated_at'] : null;
$deleted_at = isset($input['deleted_at']) ? $input['deleted_at'] : null;

// Validar campos requeridos y especificar cuáles faltan
$missing_fields = [];
if (!$izena) $missing_fields[] = 'izena';
if (!$abizena) $missing_fields[] = 'abizena';
if (!$pasahitza) $missing_fields[] = 'pasahitza';
if (!$email) $missing_fields[] = 'email';

if (!empty($missing_fields)) {
    http_response_code(400);
    echo json_encode(['error' => 'Faltan campos requeridos: ' . implode(', ', $missing_fields)]);
    exit;
}

// Verificar que la tabla langilea existe y tiene las columnas correctas
try {
    $stmt = $pdo->query("DESCRIBE langilea");
    $columns = $stmt->fetchAll(PDO::FETCH_COLUMN);
    file_put_contents('debug.log', "Columnas de la tabla langilea: " . implode(", ", $columns) . "\n", FILE_APPEND);

    if (!in_array('id', $columns) || !in_array('email', $columns)) {
        http_response_code(500);
        echo json_encode(['error' => 'Las columnas id o email no existen en la tabla langilea']);
        exit;
    }
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Error al verificar la tabla langilea: ' . $e->getMessage()]);
    exit;
}

// Buscar si el trabajador ya existe por email
try {
    $stmt = $pdo->prepare("SELECT id FROM langilea WHERE email = :email AND deleted_at IS NULL");
    $stmt->execute([':email' => $email]);
    $existing_worker = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($existing_worker) {
        // Actualizar el trabajador existente
        $query = "UPDATE langilea 
                  SET izena = :izena, abizena = :abizena, pasahitza = :pasahitza, 
                      nivel_Permisos = :nivel_Permisos, txat_permiso = :txat_permiso, 
                      updated_at = NOW(), deleted_at = :deleted_at 
                  WHERE email = :email";
        $stmt = $pdo->prepare($query);
        $stmt->execute([
            ':izena' => $izena,
            ':abizena' => $abizena,
            ':pasahitza' => $pasahitza,
            ':nivel_Permisos' => $nivel_Permisos,
            ':txat_permiso' => $txat_permiso ? 1 : 0,
            ':deleted_at' => $deleted_at,
            ':email' => $email
        ]);

        http_response_code(200);
        echo json_encode([
            'message' => 'Trabajador actualizado exitosamente',
            'worker_id' => (int)$existing_worker['id']
        ]);
    } else {
        // Crear un nuevo trabajador (ignorar worker_id, dejar que MySQL genere el id)
        $query = "INSERT INTO langilea (izena, abizena, pasahitza, email, nivel_Permisos, txat_permiso, created_at, updated_at, deleted_at) 
                  VALUES (:izena, :abizena, :pasahitza, :email, :nivel_Permisos, :txat_permiso, NOW(), :updated_at, :deleted_at)";
        $stmt = $pdo->prepare($query);
        $stmt->execute([
            ':izena' => $izena,
            ':abizena' => $abizena,
            ':pasahitza' => $pasahitza,
            ':email' => $email,
            ':nivel_Permisos' => $nivel_Permisos,
            ':txat_permiso' => $txat_permiso ? 1 : 0,
            ':updated_at' => $updated_at,
            ':deleted_at' => $deleted_at
        ]);

        // Obtener el ID del nuevo trabajador
        $new_worker_id = $pdo->lastInsertId();

        http_response_code(201);
        echo json_encode([
            'message' => 'Trabajador creado exitosamente',
            'worker_id' => (int)$new_worker_id
        ]);
    }
} catch (PDOException $e) {
    if (strpos($e->getMessage(), 'Duplicate entry') !== false && strpos($e->getMessage(), 'email') !== false) {
        http_response_code(409);
        echo json_encode(['error' => "El email $email ya existe"]);
    } else {
        http_response_code(500);
        echo json_encode(['error' => 'Error al guardar el trabajador: ' . $e->getMessage()]);
    }
}
?>