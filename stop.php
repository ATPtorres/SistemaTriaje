<?php
/**
 * stop.php - Detiene el servidor FastAPI del Sistema de Triaje
 */

$port = 8000;
$netstat = shell_exec("netstat -ano | findstr :$port");
if (preg_match_all('/\s(\d+)$/', $netstat, $matches)) {
    foreach (array_unique($matches[1]) as $pid) {
        shell_exec("taskkill /PID $pid /F 2>nul");
    }
}

echo "<!DOCTYPE html><html><head><meta charset='UTF-8'><meta http-equiv='refresh' content='2;url=index.php'><title>Triaje</title>";
echo "<style>body{font-family:sans-serif;background:#ffffff;color:#111827;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}";
echo ".box{background:#ffffff;border:1px solid #e5e7eb;padding:2rem 3rem;border-radius:12px;text-align:center}";
echo ".ok{color:#d97706;font-size:1.5rem} a{color:#2563eb;text-decoration:none}</style></head><body>";
echo "<div class='box'><p class='ok'>Servidor detenido</p><p>Redirigiendo...</p></div></body></html>";
