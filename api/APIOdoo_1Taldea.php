<?php

$servername = "localhost:3306";
$username = "root";
$password = "1WMG2023";
$database = "5_erronka1";

$conn = new mysqli($servername, $username, $password, $database);
if ($conn->connect_error) {
    die("Konexioaren akatsa: " . $conn->connect_error);
}

$sql = "SELECT izena, abizena, email FROM langilea WHERE deleted_at IS NULL";
$result = $conn->query($sql);

$langileak = [];
if ($result->num_rows > 0) {
    while ($row = $result->fetch_assoc()) {
        $langileak[] = [
            "izena" => $row["izena"] . " " . $row["abizena"],
            "email" => $row["email"]
        ];
    }
} else {
    echo "Ez dira langileak aurkitu";
    exit;
}
$conn->close();

echo json_encode($langileak, JSON_PRETTY_PRINT);

function oddoraBidali($langileak) {
    $url = "https://localhost:8085/jsonrpc";
    $db = "haimar-gelan";
    $username = "hai_ari_mor@goierrieskola.org";
    $password = "123456";

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, "$url/common/login");
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
        "jsonrpc" => "2.0",
        "method" => "call",
        "params" => [
            "db" => $db,
            "login" => $username,
            "password" => $password
        ]
    ]));
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    $response = json_decode(curl_exec($ch), true);
    $uid = $response['result'];

    foreach ($langileak as $langilea) {
        $data = [
            "jsonrpc" => "2.0",
            "method" => "call",
            "params" => [
                "service" => "object",
                "method" => "execute",
                "args" => [
                    $db,
                    $uid,
                    $password,
                    "res.partner",
                    "create",
                    [$langilea]
                ]
            ]
        ];

        curl_setopt($ch, CURLOPT_URL, "$url/object");
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
        $response = json_decode(curl_exec($ch), true);

        echo "Oddoren erantzuna {$langilea['izena']}: " . print_r($response, true) . "\n";
    }

    curl_close($ch);
}

oddoraBidali($langileak);
?>