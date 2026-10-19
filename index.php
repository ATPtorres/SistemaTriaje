<?php
/**
 * index.php - Panel de control del Sistema de Triaje
 * 
 * Verifica el estado del servidor y muestra acceso directo.
 */
$port = 8000;
$status = false;
$stats = null;

// Verificar si el servidor esta corriendo
$health = @file_get_contents("http://localhost:$port/health");
if ($health !== false) {
    $status = true;
    $stats = json_decode($health, true);
}

// Obtener estadisticas si esta conectado
$dashboard = null;
if ($status) {
    $dash = @file_get_contents("http://localhost:$port/statistics");
    if ($dash) $dashboard = json_decode($dash, true);
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistema Experto de Triaje - Panel de Control</title>
    <style>
        :root {
            --bg: #ffffff;
            --bg2: #f8f9fa;
            --card: #ffffff;
            --border: #e5e7eb;
            --text: #111827;
            --text2: #6b7280;
            --accent: #2563eb;
            --green: #16a34a;
            --red: #dc2626;
            --orange: #f97316;
            --yellow: #eab308;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        .header {
            background: var(--bg);
            border-bottom: 1px solid var(--border);
            padding: 1rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-left { display: flex; align-items: center; gap: 1rem; }
        .logo {
            width: 36px; height: 36px;
            background: var(--accent);
            border-radius: 8px;
            display: grid; place-items: center;
            font-weight: 800; font-size: 1rem; color: #fff;
        }
        .header h1 { font-size: 1.1rem; font-weight: 600; }

        .status-badge {
            display: flex; align-items: center; gap: 0.5rem;
            padding: 0.375rem 0.875rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .status-badge.online {
            background: rgba(22,163,74,0.08);
            border: 1px solid rgba(22,163,74,0.25);
            color: #16a34a;
        }
        .status-badge.offline {
            background: rgba(220,38,38,0.06);
            border: 1px solid rgba(220,38,38,0.25);
            color: #dc2626;
        }
        .status-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
        }
        .status-dot.on { background: #22c55e; }
        .status-dot.off { background: #ef4444; }

        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 2rem;
        }

        .hero {
            text-align: center;
            padding: 2rem 0 3rem;
        }
        .hero h2 {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: var(--text);
        }
        .hero p { color: var(--text2); font-size: 1rem; }

        .actions {
            display: flex;
            gap: 1rem;
            justify-content: center;
            margin-bottom: 3rem;
            flex-wrap: wrap;
        }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            text-decoration: none;
            border: none;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn:hover { opacity: 0.9; }
        .btn-primary {
            background: var(--accent);
            color: #fff;
        }
        .btn-primary:hover { background: #1d4ed8; }
        .btn-success {
            background: var(--green);
            color: #fff;
        }
        .btn-success:hover { background: #15803d; }
        .btn-danger {
            background: #fff;
            color: #dc2626;
            border: 1px solid rgba(220,38,38,0.3);
        }
        .btn-danger:hover { background: rgba(220,38,38,0.05); }
        .btn-outline {
            background: #fff;
            color: var(--text2);
            border: 1px solid var(--border);
        }
        .btn-outline:hover { border-color: var(--accent); color: var(--accent); }
        .btn-swagger {
            background: #fff;
            color: #16a34a;
            border: 1px solid rgba(22,163,74,0.3);
        }
        .btn-swagger:hover { background: rgba(22,163,74,0.05); }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1.25rem;
        }
        .card-label {
            font-size: 0.75rem;
            color: var(--text2);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        .card-value {
            font-size: 1.75rem;
            font-weight: 700;
            font-variant-numeric: tabular-nums;
        }
        .card-sub { font-size: 0.8rem; color: var(--text2); margin-top: 0.25rem; }

        .links {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }
        .link-card {
            display: flex;
            align-items: center;
            gap: 1rem;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1.25rem;
            text-decoration: none;
            color: var(--text);
            transition: all 0.2s;
        }
        .link-card:hover {
            border-color: var(--accent);
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        .link-icon {
            width: 44px; height: 44px;
            border-radius: 8px;
            display: grid; place-items: center;
            font-size: 1rem;
            flex-shrink: 0;
            font-weight: 700;
        }
        .link-info h3 { font-size: 0.95rem; font-weight: 600; }
        .link-info p { font-size: 0.8rem; color: var(--text2); margin-top: 0.125rem; }

        .footer {
            text-align: center;
            padding: 2rem;
            color: var(--text2);
            font-size: 0.8rem;
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }

        @media (max-width: 640px) {
            .header { padding: 1rem; }
            .container { padding: 1rem; }
            .hero h2 { font-size: 1.5rem; }
            .actions { flex-direction: column; align-items: stretch; }
            .btn { justify-content: center; }
            .links { grid-template-columns: 1fr; }
        }

        .lang-toggle {
            display: flex;
            border: 1px solid var(--border);
            border-radius: 9999px;
            overflow: hidden;
            margin-right: 0.75rem;
        }
        .lang-btn {
            padding: 0.25rem 0.75rem;
            font-size: 0.75rem;
            font-weight: 600;
            background: transparent;
            border: none;
            cursor: pointer;
            color: var(--text2);
            font-family: inherit;
        }
        .lang-btn.active { background: var(--accent); color: #fff; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <div class="logo">T</div>
            <h1 data-i18n="title">Sistema Experto de Triaje</h1>
        </div>
        <div style="display:flex;align-items:center">
            <div class="lang-toggle" id="langToggle">
                <button type="button" class="lang-btn active" data-lang="es" onclick="setLang('es')">ES</button>
                <button type="button" class="lang-btn" data-lang="qu" onclick="setLang('qu')">QU</button>
            </div>
            <div class="status-badge <?= $status ? 'online' : 'offline' ?>">
                <div class="status-dot <?= $status ? 'on' : 'off' ?>"></div>
                <?= $status ? 'Online' : 'Offline' ?>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="hero">
            <h2 data-i18n="panel">Panel de Control</h2>
            <p data-i18n="subtitle">Sistema Experto de Triaje Medico - MySQL + FastAPI + Python</p>
        </div>

        <div class="actions">
            <?php if ($status): ?>
                <a href="http://localhost:<?= $port ?>" target="_blank" class="btn btn-primary" data-i18n="open">
                    Abrir Sistema
                </a>
                <a href="http://localhost:<?= $port ?>/docs" target="_blank" class="btn btn-swagger" data-i18n="swagger">
                    Swagger API
                </a>
                <a href="stop.php" class="btn btn-danger" data-i18n="stop">
                    Detener Servidor
                </a>
            <?php else: ?>
                <a href="start.php" class="btn btn-success" data-i18n="start">
                    Iniciar Servidor
                </a>
                <a href="http://localhost/phpmyadmin" target="_blank" class="btn btn-outline" data-i18n="phpmyadmin">
                    phpMyAdmin
                </a>
            <?php endif; ?>
        </div>

        <?php if ($status && $dashboard): ?>
        <div class="grid">
            <div class="card">
                <div class="card-label" data-i18n="patients">Pacientes</div>
                <div class="card-value"><?= $dashboard['total_pacientes'] ?? 0 ?></div>
            </div>
            <div class="card">
                <div class="card-label" data-i18n="today">Evaluaciones Hoy</div>
                <div class="card-value"><?= $dashboard['evaluaciones_hoy'] ?? 0 ?></div>
            </div>
            <div class="card">
                <div class="card-label" data-i18n="total_evals">Total Evaluaciones</div>
                <div class="card-value"><?= $dashboard['total_evaluaciones'] ?? 0 ?></div>
            </div>
            <div class="card">
                <div class="card-label" data-i18n="avg_time">Tiempo Promedio</div>
                <div class="card-value"><?= ($dashboard['tiempo_promedio_ms'] ?? 0) ?>ms</div>
            </div>
        </div>

        <?php if (!empty($dashboard['distribucion_niveles'])): ?>
        <div class="card" style="margin-bottom:2rem">
            <div class="card-label" style="margin-bottom:1rem">Distribucion por Nivel</div>
            <?php
            $colors = ['Nivel 1' => '#ef4444', 'Nivel 2' => '#f97316', 'Nivel 3' => '#eab308', 'Nivel 4' => '#22c55e', 'Nivel 5' => '#3b82f6'];
            $dist = $dashboard['distribucion_niveles'];
            $total = max(array_sum($dist), 1);
            foreach ($dist as $nivel => $count):
                $pct = round(($count / $total) * 100);
                $color = $colors[$nivel] ?? '#666';
            ?>
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem">
                <span style="width:50px;font-size:0.8rem;color:var(--text2)"><?= $nivel ?></span>
                <div style="flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden">
                    <div style="height:100%;width:<?= $pct ?>%;background:<?= $color ?>;border-radius:4px;transition:width 0.5s"></div>
                </div>
                <span style="width:30px;font-size:0.8rem;color:var(--text2);text-align:right"><?= $count ?></span>
            </div>
            <?php endforeach; ?>
        </div>
        <?php endif; ?>
        <?php endif; ?>

        <div class="links">
            <a href="http://localhost:<?= $port ?>" target="_blank" class="link-card">
                <div class="link-icon" style="background:#eff6ff;color:#2563eb">+</div>
                <div class="link-info">
                    <h3 data-i18n="link_ui">Interfaz de Triaje</h3>
                    <p data-i18n="link_ui_desc">Evaluar pacientes en tiempo real</p>
                </div>
            </a>
            <a href="http://localhost:<?= $port ?>/docs" target="_blank" class="link-card">
                <div class="link-icon" style="background:#f0fdf4;color:#16a34a">/</div>
                <div class="link-info">
                    <h3 data-i18n="link_docs">Documentacion API</h3>
                    <p data-i18n="link_docs_desc">Swagger UI - Probar endpoints</p>
                </div>
            </a>
            <a href="http://localhost/phpmyadmin" target="_blank" class="link-card">
                <div class="link-icon" style="background:#fff7ed;color:#ea580c">DB</div>
                <div class="link-info">
                    <h3>phpMyAdmin</h3>
                    <p data-i18n="link_db">Base de datos: triaje_sistema</p>
                </div>
            </a>
            <a href="http://localhost:<?= $port ?>/knowledge-base" target="_blank" class="link-card">
                <div class="link-icon" style="background:#faf5ff;color:#9333ea">KB</div>
                <div class="link-info">
                    <h3 data-i18n="link_kb">Base de Conocimiento</h3>
                    <p data-i18n="link_kb_desc">19 reglas IF-THEN del sistema experto</p>
                </div>
            </a>
        </div>
    </div>

    <div class="footer">
        <span data-i18n="footer">Sistema Experto de Triaje v3.0.0 - FastAPI + MySQL + Python</span> | 
        <a href="start.php" style="color:var(--text2)" data-i18n="restart">Reiniciar</a>
    </div>

<script>
let LANG = localStorage.getItem('triaje_lang') || 'es';
const I18N = {
  es: {
    title: 'Sistema Experto de Triaje',
    panel: 'Panel de Control',
    subtitle: 'Sistema Experto de Triaje Medico - MySQL + FastAPI + Python',
    open: 'Abrir Sistema',
    swagger: 'Swagger API',
    stop: 'Detener Servidor',
    start: 'Iniciar Servidor',
    phpmyadmin: 'phpMyAdmin',
    patients: 'Pacientes',
    today: 'Evaluaciones Hoy',
    total_evals: 'Total Evaluaciones',
    avg_time: 'Tiempo Promedio',
    link_ui: 'Interfaz de Triaje',
    link_ui_desc: 'Evaluar pacientes en tiempo real',
    link_docs: 'Documentacion API',
    link_docs_desc: 'Swagger UI - Probar endpoints',
    link_db: 'Base de datos: triaje_sistema',
    link_kb: 'Base de Conocimiento',
    link_kb_desc: '19 reglas IF-THEN del sistema experto',
    footer: 'Sistema Experto de Triaje v3.0.0 - FastAPI + MySQL + Python',
    restart: 'Reiniciar',
  },
  qu: {
    title: 'Triaje Yachaq Systema',
    panel: 'Kbaw Tarkiy',
    subtitle: 'Triaje Yachaq Systema - MySQL + FastAPI + Python',
    open: 'Sistema Lliwta',
    swagger: 'Swagger API',
    stop: 'Sistema Taqtiy',
    start: 'Sistema Kallariy',
    phpmyadmin: 'phpMyAdmin',
    patients: 'Ukuqkuna',
    today: "Rikch'aykuna kunan pacha",
    total_evals: "Rikch'aykuna llapan",
    avg_time: 'Promedio tiempo',
    link_ui: "Triaje Qhatu",
    link_ui_desc: "Ukuqkunata kunan pachaman rikch'ay",
    link_docs: 'API Documentation',
    link_docs_desc: 'Swagger UI - endpoints rikch\'ay',
    link_db: 'Base de datos: triaje_sistema',
    link_kb: 'Yachay Karkana',
    link_kb_desc: '19 IF-THEN reglas sistema experto',
    footer: 'Triaje Yachaq Systema v3.0.0 - FastAPI + MySQL + Python',
    restart: 'Kallariy',
  }
};
function t(k){ return (I18N[LANG]&&I18N[LANG][k])||I18N.es[k]||k; }
function setLang(lang){
  LANG = lang==='qu'?'qu':'es';
  localStorage.setItem('triaje_lang', LANG);
  document.documentElement.lang = LANG==='qu'?'qu':'es';
  applyI18n();
  document.querySelectorAll('.lang-btn').forEach(b=>b.classList.toggle('active', b.dataset.lang===LANG));
}
function applyI18n(){
  document.querySelectorAll('[data-i18n]').forEach(el=>{
    el.textContent = t(el.getAttribute('data-i18n'));
  });
}
if (LANG==='qu') setLang('qu');
</script>
</body>
</html>
