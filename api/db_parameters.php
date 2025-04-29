
<?php
$servername = "localhost:3306";
$username = "root";
$password = "1WMG2023";
$database = "5_erronka";

$conn = new mysqli($servername, $username, $password, $database);
if ($conn->connect_error) {
    die("Konexioaren akatsa: " . $conn->connect_error);
}
