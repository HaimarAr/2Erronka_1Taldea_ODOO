<?php
require("db_parameters.php");
header('Content-Type: application/json; charset=utf-8');

ini_set('display_errors', 0);
error_reporting(0);

$conn->set_charset("utf8");

$response = [];
$platerak = [];

try {
    if (isset($_GET['id']) && !empty($_GET['id'])) {
        $id = $conn->real_escape_string($_GET['id']);
        $sql = "SELECT * FROM platera WHERE id = '$id'";
        $result = $conn->query($sql);

        if ($result && $result->num_rows > 0) {
            $platera = $result->fetch_assoc();
            // Formatea las fechas si es necesario
            if ($platera['created_at']) {
                $platera['created_at'] = date('Y-m-d H:i:s', strtotime($platera['created_at']));
            }
            if ($platera['updated_at']) {
                $platera['updated_at'] = date('Y-m-d H:i:s', strtotime($platera['updated_at']));
            }
            if ($platera['deleted_at']) {
                $platera['deleted_at'] = date('Y-m-d H:i:s', strtotime($platera['deleted_at']));
            }
            $response = [
                'status_code' => 200,
                'platera' => $platera
            ];
        } else {
            $response = [
                'status_code' => 404,
                'mezua' => 'Ez da platerarik aurkitu ID honekin: ' . $id
            ];
        }
    } else {
        $sql = "SELECT * FROM platera";
        $result = $conn->query($sql);

        if ($result && $result->num_rows > 0) {
            while ($row = $result->fetch_assoc()) {
                // Formatea las fechas si es necesario
                if ($row['created_at']) {
                    $row['created_at'] = date('Y-m-d H:i:s', strtotime($row['created_at']));
                }
                if ($row['updated_at']) {
                    $row['updated_at'] = date('Y-m-d H:i:s', strtotime($row['updated_at']));
                }
                if ($row['deleted_at']) {
                    $row['deleted_at'] = date('Y-m-d H:i:s', strtotime($row['deleted_at']));
                }
                $platerak[] = $row;
            }
            $response = [
                'status_code' => 200,
                'platerak' => $platerak
            ];
        } else {
            $response = [
                'status_code' => 200,
                'platerak' => []
            ];
        }
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