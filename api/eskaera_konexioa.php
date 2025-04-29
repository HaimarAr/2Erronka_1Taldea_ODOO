<?php

require("db_parameters.php");

$id = isset($_GET['id']) ? $_GET['id'] : null;

if ($id) {
    $sql = "SELECT * FROM eskaera WHERE id = ?";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("i", $id);
    $stmt->execute();
    $result = $stmt->get_result();
    
    if ($result->num_rows > 0) {
        $row = $result->fetch_assoc();
        echo json_encode([
            "status_code" => 200,
            "eskaera" => $row
        ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    } else {
        echo json_encode(["status_code" => 404, "mezua" => "Eskaera ez da aurkitu"]);
    }
} else {
    $sql = "SELECT * FROM eskaera";
    $result = $conn->query($sql);
    
    $eskaerak = [];
    if ($result && $result->num_rows > 0) {
        while ($row = $result->fetch_assoc()) {
            $eskaerak[] = $row;
        }
    }
    echo json_encode(["status_code" => 200, "eskaerak" => $eskaerak], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
}

$conn->close();

?>