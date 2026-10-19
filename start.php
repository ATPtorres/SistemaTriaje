<?php
/**
 * start.php - Inicia el servidor FastAPI del Sistema de Triaje
 * 
 * Ejecuta uvicorn en background via PHP exec().
 * Acceder desde: http://localhost/triaje/start.php
 */

$python = 'C:\\Users\\Superuser\\AppData\\Local\\Programs\\Python\\Python312\\python.exe';
$project_dir = __DIR__;
$port = 8000;

// Verificar si ya esta corriendo
$checking = @file_get_contents("http://localhost:$port/health");
if ($checking !== false) {
    echo "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Triaje</title>";
    echo "<style>body{font-family:sans-serif;background:#ffffff;color:#111827;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}";
    echo ".box{background:#ffffff;border:1px solid #e5e7eb;padding:2rem 3rem;border-radius:12px;text-align:center}";
    echo ".ok{color:#16a34a;font-size:1.5rem} a{color:#2563eb;text-decoration:none}</style></head><body>";
    echo "<div class='box'><p class='ok'>El servidor ya esta corriendo</p>";
    echo "<p><a href='index.php'>Ir al Sistema de Triaje</a></p>";
    echo "<p><small>Puerto: $port</small></p></div></body></html>";
    exit;
}

// Matar procesos anteriores en el puerto
$netstat = shell_exec("netstat -ano | findstr :$port");
if (preg_match_all('/\s(\d+)$/', $netstat, $matches)) {
    foreach (array_unique($matches[1]) as $pid) {
        shell_exec("taskkill /PID $pid /F 2>nul");
    }
}
sleep(1);

// Iniciar uvicorn en background
$cmd = "start /B cmd /c \"\"$python\" -m uvicorn main:app --host 127.0.0.1 --port $port\"";
pclose(popen("cmd /c $cmd", "r"));

// Esperar a que este listo
$ready = false;
for ($i = 0; $i < 15; $i++) {
    sleep(1);
    $check = @file_get_contents("http://localhost:$port/health");
    if ($check !== false) {
        $ready = true;
        break;
    }
}

if ($ready) {
    echo "<!DOCTYPE html><html><head><meta charset='UTF-8'><meta http-equiv='refresh' content='2;url=index.php'><title>Triaje</title>";
    echo "<style>body{font-family:sans-serif;background:#ffffff;color:#111827;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}";
    echo ".box{background:#ffffff;border:1px solid #e5e7eb;padding:2rem 3rem;border-radius:12px;text-align:center}";
    echo ".ok{color:#16a34a;font-size:1.5rem} a{color:#2563eb;text-decoration:none}</style></head><body>";
    echo "<div class='box'><p class='ok'>Servidor iniciado correctamente</p>";
    echo "<p>Redirigiendo...</p></div></body></html>";
} else {
    echo "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Triaje - Error</title>";
    echo "<style>body{font-family:sans-serif;background:#ffffff;color:#111827;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}";
    echo ".box{background:#ffffff;border:1px solid #e5e7eb;padding:2rem 3rem;border-radius:12px;text-align:center}";
    echo ".err{color:#dc2626;font-size:1.5rem} a{color:#2563eb;text-decoration:none}</style></head><body>";
    echo "<div class='box'><p class='err'>Error al iniciar el servidor</p>";
    echo "<p>Verifica que Python y las dependencias esten instaladas.</p>";
    echo "<p><a href='index.php'>Volver</a></p></div></body></html>";
}
