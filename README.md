# Proyecto Trivias (FastAPI + HTML + SQLite3)

Aplicación web de trivias con preguntas de opción múltiple, registro de usuarios, registro de partidas y panel de administración.

## Requisitos

- Python 3.10 o superior
- pip

## Instalación

1. (Opcional pero recomendado) Crear y activar un entorno virtual:

   **Windows (PowerShell):**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **Windows (CMD):**
   ```cmd
   py -m venv .venv
   .venv\Scripts\activate.bat
   ```

2. Instalar dependencias:

   ```bash
   pip install -r requirements.txt
   ```

## Ejecución

Inicia el servidor con cualquiera de estas opciones:

- Directamente con Python:
  ```bash
  python main.py
  ```
  o, si usas el lanzador de Windows:
  ```bash
  py main.py
  ```

- Con Uvicorn (recomendado en desarrollo, con recarga automática):
  ```bash
  uvicorn main:app --reload
  ```

Luego abre en el navegador: [http://127.0.0.1:8000](http://127.0.0.1:8000)

En Windows también puedes usar el script `run.bat` (instala dependencias y arranca el servidor).

## Estructura del proyecto

```
.
├── main.py            # Aplicación FastAPI y lógica con SQLite3
├── questions.db       # Base de datos SQLite (se actualiza al ejecutar)
├── requirements.txt   # Dependencias
├── run.bat            # Script de arranque para Windows
└── templates/         # Plantillas HTML (Jinja2)
    ├── index.html
    ├── crear.html
    ├── buscar.html
    ├── detalle.html
    ├── editar.html
    ├── trivia.html
    ├── jugar.html
    ├── resultado.html
    ├── registro.html
    ├── admin.html
    ├── admin_trivias.html
    ├── admin_preguntas.html
    ├── admin_usuarios.html
    └── admin_trivias_usuarios.html
```

## Funcionalidades

- **Inicio**: listado de géneros con contador de preguntas.
- **CRUD**: crear, buscar, ver, editar y eliminar preguntas por género (con respuesta correcta y 3 incorrectas).
- **Jugar**: trivia de opción múltiple por género o con todas las preguntas, con marcador y guardado de partidas por usuario.
- **Registro**: alta de usuarios para guardar resultados.
- **Admin** (`/admin`): gestión de trivias, preguntas, usuarios y consulta de partidas jugadas.

La base de datos `questions.db` y las tablas necesarias se crean/migran automáticamente al iniciar la aplicación.
