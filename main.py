import random
import sqlite3
from datetime import datetime
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

# Configuración de Jinja2 — busca los templates HTML en la carpeta "templates/"
templates = Jinja2Templates(directory="templates")

app = FastAPI()

NOMBRE_DB = "questions.db"


def conectar_db():
    """Abre una conexión nueva a la base de datos (una por vista)."""
    conn = sqlite3.connect(NOMBRE_DB)
    conn.row_factory = sqlite3.Row  # permite leer las columnas por nombre
    return conn


def inicializar_db():
    """Crea las tablas si todavía no existen."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trivia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pregunta TEXT NOT NULL UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pregunta TEXT NOT NULL,
        respuesta TEXT NOT NULL,
        incorrecta1 TEXT,
        incorrecta2 TEXT,
        incorrecta3 TEXT,
        trivia_id INTEGER NOT NULL,
        FOREIGN KEY (trivia_id) REFERENCES trivia(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS game_trivia (
        game_id INTEGER NOT NULL,
        trivia_id INTEGER NOT NULL,
        PRIMARY KEY (game_id, trivia_id),
        FOREIGN KEY (game_id) REFERENCES questions(id),
        FOREIGN KEY (trivia_id) REFERENCES trivia(id)
    )
    """)

    # Migración: si la tabla questions ya existía sin las respuestas falsas,
    # le añadimos las columnas nuevas sin borrar los datos
    cursor.execute("PRAGMA table_info(questions)")
    columnas = [fila["name"] for fila in cursor.fetchall()]
    for nombre in ("incorrecta1", "incorrecta2", "incorrecta3"):
        if nombre not in columnas:
            cursor.execute(f"ALTER TABLE questions ADD COLUMN {nombre} TEXT")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS partidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        trivia_id INTEGER,
        aciertos INTEGER NOT NULL,
        total INTEGER NOT NULL,
        fecha TEXT NOT NULL,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY (trivia_id) REFERENCES trivia(id)
    )
    """)
    conn.commit()
    conn.close()


def obtener_o_crear_trivia(cursor, conn, trivia_pregunta):
    """Devuelve el id de la trivia y, si no existe, la crea."""
    cursor.execute("SELECT id FROM trivia WHERE pregunta = ?", (trivia_pregunta,))
    row = cursor.fetchone()
    if row:
        return row["id"]
    cursor.execute("INSERT INTO trivia (pregunta) VALUES (?)", (trivia_pregunta,))
    conn.commit()
    return cursor.lastrowid


def obtener_o_crear_usuario(cursor, conn, nombre):
    """Devuelve el id del usuario y, si no existe, lo registra."""
    cursor.execute("SELECT id FROM usuarios WHERE nombre = ?", (nombre,))
    row = cursor.fetchone()
    if row:
        return row["id"]
    cursor.execute("INSERT INTO usuarios (nombre) VALUES (?)", (nombre,))
    conn.commit()
    return cursor.lastrowid


# ============================================================
# VISTAS
# ============================================================

@app.get("/")
def listar_generos(request: Request):
    """Página de inicio: lista los géneros de trivia con sus preguntas."""
    conn = conectar_db()
    cursor = conn.cursor()
    query = """
    SELECT f.id, f.pregunta AS genero, COUNT(h.id) AS total
    FROM trivia f
    LEFT JOIN questions h ON h.trivia_id = f.id
    GROUP BY f.id
    ORDER BY f.pregunta
    """
    cursor.execute(query)
    generos = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return templates.TemplateResponse(
        request, name="index.html", context={"generos": generos}
    )


@app.get("/crear")
def crear_game(
    request: Request,
    pregunta: str = "",
    respuesta: str = "",
    incorrecta1: str = "",
    incorrecta2: str = "",
    incorrecta3: str = "",
    trivia_pregunta: str = "",
):
    """Muestra el formulario y, si llegan datos, guarda la pregunta."""
    if not pregunta or not respuesta or not trivia_pregunta:
        # Primera visita: solo mostramos el formulario vacío
        return templates.TemplateResponse(request, name="crear.html", context={})

    # Limpiamos las respuestas falsas: sin repetir y sin igualar a la correcta
    respuestas_falsas = []
    for candidata in (incorrecta1, incorrecta2, incorrecta3):
        candidata = candidata.strip()
        repetida = any(
            candidata.lower() == otra.lower()
            for otra in respuestas_falsas + [respuesta]
            if otra
        )
        respuestas_falsas.append(candidata if candidata and not repetida else None)

    conn = conectar_db()
    cursor = conn.cursor()
    trivia_id = obtener_o_crear_trivia(cursor, conn, trivia_pregunta)
    cursor.execute(
        "INSERT INTO questions (pregunta, respuesta, incorrecta1, incorrecta2, incorrecta3, trivia_id) VALUES (?, ?, ?, ?, ?, ?)",
        (pregunta, respuesta, respuestas_falsas[0], respuestas_falsas[1], respuestas_falsas[2], trivia_id),
    )
    conn.commit()
    conn.close()

    # Volvemos al inicio para ver la pregunta guardada
    return RedirectResponse("/", status_code=303)


@app.get("/buscar")
def buscar_trivia(request: Request, busqueda: str = ""):
    """Busca por ID o por texto y muestra los resultados en la misma página."""
    conn = conectar_db()
    cursor = conn.cursor()
    query = """
    SELECT h.id, h.pregunta, h.respuesta, f.pregunta AS trivia
    FROM questions h
    LEFT JOIN trivia f ON h.trivia_id = f.id
    """
    questions = []

    if busqueda:
        if busqueda.isdigit():
            cursor.execute(query + " WHERE h.id = ?", (int(busqueda),))
        else:
            cursor.execute(
                query + " WHERE LOWER(h.pregunta) LIKE ?",
                (f"%{busqueda.lower()}%",),
            )
        questions = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return templates.TemplateResponse(
        request,
        name="buscar.html",
        context={"busqueda": busqueda, "questions": questions},
    )


@app.get("/questions/{game_id}")
def ver_question(request: Request, game_id: int):
    """Detalle de una pregunta."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT h.id, h.pregunta, h.respuesta, f.pregunta AS trivia
        FROM questions h
        LEFT JOIN trivia f ON h.trivia_id = f.id
        WHERE h.id = ?
        """,
        (game_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")

    return templates.TemplateResponse(
        request, name="detalle.html", context={"q": dict(row)}
    )


@app.get("/questions/{game_id}/editar")
def actualizar_game(
    request: Request,
    game_id: int,
    nuevo_pregunta: str = "",
    nuevo_respuesta: str = "",
    incorrecta1: str = "",
    incorrecta2: str = "",
    incorrecta3: str = "",
    nueva_genero: str = "",
):
    """Muestra el formulario con los valores actuales y guarda los cambios."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT h.id, h.pregunta, h.respuesta, h.incorrecta1, h.incorrecta2, h.incorrecta3,
               f.pregunta AS trivia
        FROM questions h
        LEFT JOIN trivia f ON h.trivia_id = f.id
        WHERE h.id = ?
        """,
        (game_id,),
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")

    pregunta_actual = row["pregunta"]
    respuesta_actual = row["respuesta"]
    genero_actual = row["trivia"] or ""

    # Primera visita: solo mostramos el formulario con los valores actuales
    if not nuevo_pregunta:
        conn.close()
        return templates.TemplateResponse(
            request,
            name="editar.html",
            context={"q": dict(row)},
        )

    # Si un campo llega vacío, conservamos el valor actual
    if not nuevo_respuesta:
        nuevo_respuesta = respuesta_actual
    if not nueva_genero:
        nueva_genero = genero_actual

    # Limpiamos las respuestas falsas: sin repetir y sin igualar a la correcta
    respuestas_falsas = []
    for candidata in (incorrecta1, incorrecta2, incorrecta3):
        candidata = candidata.strip()
        repetida = any(
            candidata.lower() == otra.lower()
            for otra in respuestas_falsas + [nuevo_respuesta]
            if otra
        )
        respuestas_falsas.append(candidata if candidata and not repetida else None)

    trivia_id = obtener_o_crear_trivia(cursor, conn, nueva_genero)
    cursor.execute(
        "UPDATE questions SET pregunta = ?, respuesta = ?, incorrecta1 = ?, incorrecta2 = ?, incorrecta3 = ?, trivia_id = ? WHERE id = ?",
        (nuevo_pregunta, nuevo_respuesta, respuestas_falsas[0], respuestas_falsas[1], respuestas_falsas[2], trivia_id, game_id),
    )
    conn.commit()
    conn.close()

    # Volvemos al detalle de la pregunta editada
    return RedirectResponse(f"/questions/{game_id}", status_code=303)


@app.get("/questions/{game_id}/eliminar")
def eliminar_game(game_id: int, volver: str = ""):
    """Elimina una pregunta y vuelve al inicio (o al panel si venimos de ahí)."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE id = ?", (game_id,))
    conn.commit()
    conn.close()
    destino = "/admin/preguntas" if volver == "admin" else "/"
    return RedirectResponse(destino, status_code=303)


@app.get("/trivia")
def obtener_questions_genero(request: Request, genero: str = ""):
    """Lista las preguntas de un género de trivia (con la misma página de búsqueda)."""
    conn = conectar_db()
    cursor = conn.cursor()
    questions = []
    genero_encontrado = False

    if genero:
        cursor.execute(
            "SELECT id FROM trivia WHERE LOWER(pregunta) = LOWER(?)", (genero,)
        )
        row = cursor.fetchone()
        if row:
            genero_encontrado = True
            cursor.execute(
                "SELECT id, pregunta, respuesta FROM questions WHERE trivia_id = ?",
                (row["id"],),
            )
            questions = [dict(each) for each in cursor.fetchall()]

    conn.close()

    return templates.TemplateResponse(
        request,
        name="trivia.html",
        context={
            "genero": genero,
            "genero_encontrado": genero_encontrado,
            "questions": questions,
        },
    )


@app.get("/jugar")
def jugar(
    request: Request,
    usuario: str = "",
    genero: str = "",
    todas: str = "",
    pos: int = 0,
    aciertos: int = 0,
):
    """Vista para jugar la trivia: muestra una pregunta por vez."""
    conn = conectar_db()
    cursor = conn.cursor()

    jugando = bool(genero) or todas == "1"
    questions = []
    generos = []
    genero_encontrado = True

    if jugando:
        if todas == "1":
            cursor.execute(
                "SELECT h.id, h.pregunta, h.respuesta, h.incorrecta1, h.incorrecta2, h.incorrecta3, h.trivia_id FROM questions h ORDER BY h.id"
            )
            questions = [dict(fila) for fila in cursor.fetchall()]
        else:
            cursor.execute(
                "SELECT id FROM trivia WHERE LOWER(pregunta) = LOWER(?)", (genero,)
            )
            fila = cursor.fetchone()
            if fila:
                cursor.execute(
                    "SELECT id, pregunta, respuesta, incorrecta1, incorrecta2, incorrecta3, trivia_id FROM questions WHERE trivia_id = ? ORDER BY id",
                    (fila["id"],),
                )
                questions = [dict(cada) for cada in cursor.fetchall()]
            else:
                genero_encontrado = False
    else:
        # Menú de juego: mostramos los géneros disponibles
        cursor.execute("SELECT pregunta FROM trivia ORDER BY pregunta")
        generos = [fila["pregunta"] for fila in cursor.fetchall()]

    total = len(questions)
    terminado = jugando and pos >= total
    pregunta_actual = questions[pos] if jugando and not terminado else None

    # Opciones múltiple choice para la pregunta actual.
    # Primero usamos las respuestas falsas guardadas al crear la pregunta;
    # si faltan, las completamos con respuestas de otras preguntas.
    opciones = []
    if pregunta_actual:
        correcta = pregunta_actual["respuesta"].strip()

        # Respuestas falsas guardadas con la pregunta
        otras = []
        for candidata in (
            pregunta_actual["incorrecta1"],
            pregunta_actual["incorrecta2"],
            pregunta_actual["incorrecta3"],
        ):
            candidata = (candidata or "").strip()
            if (
                candidata
                and candidata.lower() != correcta.lower()
                and all(candidata.lower() != o.lower() for o in otras)
            ):
                otras.append(candidata)

        # Si faltan, respuestas de otras preguntas del mismo género
        faltan = 3 - len(otras)
        if faltan > 0:
            cursor.execute(
                """
                SELECT respuesta FROM questions
                WHERE trivia_id = ? AND id != ? AND respuesta != ?
                GROUP BY respuesta
                ORDER BY respuesta
                LIMIT ?
                """,
                (pregunta_actual["trivia_id"], pregunta_actual["id"], correcta, faltan),
            )
            for fila in cursor.fetchall():
                candidata = fila["respuesta"].strip()
                if (
                    candidata.lower() != correcta.lower()
                    and all(candidata.lower() != o.lower() for o in otras)
                ):
                    otras.append(candidata)

        # Si aún faltan, respuestas de cualquier otra pregunta
        faltan = 3 - len(otras)
        if faltan > 0:
            cursor.execute(
                """
                SELECT respuesta FROM questions
                WHERE id != ? AND respuesta != ?
                GROUP BY respuesta
                ORDER BY respuesta
                LIMIT ?
                """,
                (pregunta_actual["id"], correcta, faltan),
            )
            for fila in cursor.fetchall():
                candidata = fila["respuesta"].strip()
                if (
                    candidata.lower() != correcta.lower()
                    and all(candidata.lower() != o.lower() for o in otras)
                ):
                    otras.append(candidata)

        # Mezclamos con semilla fija: la misma pregunta siempre muestra las mismas opciones
        opciones_texto = [correcta] + otras
        while len(opciones_texto) < 4:
            opciones_texto.append("Ninguna de las anteriores")
        random.Random(pregunta_actual["id"]).shuffle(opciones_texto)

        # Cada opción es un enlace que lleva el estado de la partida
        base = {
            "pregunta_id": pregunta_actual["id"],
            "pos": pos,
            "aciertos": aciertos,
        }
        if genero:
            base["genero"] = genero
        if todas == "1":
            base["todas"] = todas
        if usuario:
            base["usuario"] = usuario
        opciones = [
            {
                "texto": texto,
                "url": "/jugar/responder?" + urlencode({**base, "opcion": texto}),
            }
            for texto in opciones_texto
        ]

    conn.close()

    return templates.TemplateResponse(
        request,
        name="jugar.html",
        context={
            "jugando": jugando,
            "terminado": terminado,
            "usuario": usuario,
            "genero": genero,
            "todas": todas,
            "pos": pos,
            "aciertos": aciertos,
            "total": total,
            "pregunta": pregunta_actual,
            "opciones": opciones,
            "generos": generos,
            "genero_encontrado": genero_encontrado,
        },
    )


@app.get("/jugar/responder")
def responder_pregunta(
    request: Request,
    pregunta_id: int,
    opcion: str = "",
    pos: int = 0,
    genero: str = "",
    todas: str = "",
    aciertos: int = 0,
    usuario: str = "",
):
    """Comprueba la opción elegida por el jugador y prepara la siguiente pregunta."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT respuesta, trivia_id FROM questions WHERE id = ?", (pregunta_id,)
    )
    fila = cursor.fetchone()

    if not fila:
        conn.close()
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")

    respuesta_jugador = opcion.strip()
    respuesta_correcta = fila["respuesta"].strip()
    correcta = respuesta_jugador.lower() == respuesta_correcta.lower()

    if correcta:
        aciertos += 1
    pos += 1

    # ¿Era la última pregunta de la partida? Si hay jugador, guardamos la partida
    if todas == "1":
        cursor.execute("SELECT COUNT(*) AS total FROM questions")
    else:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM questions WHERE trivia_id = ?",
            (fila["trivia_id"],),
        )
    total = cursor.fetchone()["total"]

    partida_guardada = False
    if pos >= total and usuario:
        usuario_id = obtener_o_crear_usuario(cursor, conn, usuario)
        trivia_id = fila["trivia_id"] if todas != "1" else None
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        cursor.execute(
            "INSERT INTO partidas (usuario_id, trivia_id, aciertos, total, fecha) VALUES (?, ?, ?, ?, ?)",
            (usuario_id, trivia_id, aciertos, total, fecha),
        )
        conn.commit()
        partida_guardada = True

    conn.close()

    # Enlace para continuar jugando con la pregunta siguiente (lleva el marcador)
    params = {"pos": pos, "aciertos": aciertos}
    if genero:
        params["genero"] = genero
    if todas == "1":
        params["todas"] = todas
    if usuario:
        params["usuario"] = usuario
    siguiente_url = "/jugar?" + urlencode(params)

    return templates.TemplateResponse(
        request,
        name="resultado.html",
        context={
            "correcta": correcta,
            "respuesta_jugador": respuesta_jugador,
            "respuesta_correcta": respuesta_correcta,
            "siguiente_url": siguiente_url,
            "partida_guardada": partida_guardada,
            "usuario": usuario,
        },
    )


@app.get("/registro")
def registrar_usuario(request: Request, nombre: str = ""):
    """Registro de usuarios para guardar sus resultados."""
    mensaje = ""
    registrado = False

    if nombre:
        nombre = nombre.strip()
        if not nombre:
            mensaje = "El nombre no puede estar vacío."
        else:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE nombre = ?", (nombre,))
            fila = cursor.fetchone()
            if fila:
                mensaje = "Ese usuario ya está registrado."
            else:
                cursor.execute("INSERT INTO usuarios (nombre) VALUES (?)", (nombre,))
                conn.commit()
                mensaje = f"Usuario '{nombre}' registrado con éxito."
                registrado = True
            conn.close()

    return templates.TemplateResponse(
        request,
        name="registro.html",
        context={"mensaje": mensaje, "registrado": registrado, "nombre": nombre},
    )


@app.get("/admin")
def admin_panel(request: Request):
    """Panel de administración: menú con las secciones."""
    return templates.TemplateResponse(request, name="admin.html", context={})


@app.get("/admin/trivias")
def admin_trivias(request: Request, renombrar_id: int = 0, nuevo_genero: str = ""):
    """Admin — lista de trivias con sus preguntas y partidas."""
    conn = conectar_db()
    cursor = conn.cursor()

    # Renombrar una trivia (formulario de cada fila)
    if renombrar_id and nuevo_genero:
        nuevo_genero = nuevo_genero.strip()
        if nuevo_genero:
            cursor.execute(
                "SELECT id FROM trivia WHERE LOWER(pregunta) = LOWER(?)", (nuevo_genero,)
            )
            fila = cursor.fetchone()
            if not fila or fila["id"] == renombrar_id:
                cursor.execute(
                    "UPDATE trivia SET pregunta = ? WHERE id = ?",
                    (nuevo_genero, renombrar_id),
                )
                conn.commit()
        conn.close()
        return RedirectResponse("/admin/trivias", status_code=303)

    cursor.execute(
        """
        SELECT f.id, f.pregunta AS genero,
               COUNT(DISTINCT h.id) AS preguntas,
               COUNT(DISTINCT p.id) AS partidas
        FROM trivia f
        LEFT JOIN questions h ON h.trivia_id = f.id
        LEFT JOIN partidas p ON p.trivia_id = f.id
        GROUP BY f.id
        ORDER BY f.pregunta
        """
    )
    generos = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return templates.TemplateResponse(
        request, name="admin_trivias.html", context={"generos": generos}
    )


@app.get("/admin/trivias/{trivia_id}/eliminar")
def admin_eliminar_trivia(trivia_id: int):
    """Admin — elimina una trivia junto con sus preguntas."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE trivia_id = ?", (trivia_id,))
    cursor.execute("UPDATE partidas SET trivia_id = NULL WHERE trivia_id = ?", (trivia_id,))
    cursor.execute("DELETE FROM trivia WHERE id = ?", (trivia_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/trivias", status_code=303)


@app.get("/admin/preguntas")
def admin_preguntas(request: Request, genero: str = ""):
    """Admin — lista de preguntas (opcionalmente filtradas por trivia)."""
    conn = conectar_db()
    cursor = conn.cursor()
    query = """
    SELECT h.id, h.pregunta, h.respuesta, h.incorrecta1, h.incorrecta2, h.incorrecta3,
           f.pregunta AS trivia
    FROM questions h
    LEFT JOIN trivia f ON h.trivia_id = f.id
    """
    if genero:
        cursor.execute(query + " WHERE f.pregunta = ? ORDER BY h.id", (genero,))
    else:
        cursor.execute(query + " ORDER BY h.id")
    questions = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return templates.TemplateResponse(
        request,
        name="admin_preguntas.html",
        context={"questions": questions, "genero": genero},
    )


@app.get("/admin/usuarios")
def admin_usuarios(
    request: Request,
    nombre: str = "",
    renombrar_id: int = 0,
    nuevo_nombre: str = "",
):
    """Admin — lista de usuarios con sus estadísticas. También crea y renombra."""
    conn = conectar_db()
    cursor = conn.cursor()

    # Crear un usuario nuevo (formulario de la página)
    if nombre:
        nombre_nuevo = nombre.strip()
        if nombre_nuevo:
            cursor.execute(
                "SELECT id FROM usuarios WHERE LOWER(nombre) = LOWER(?)", (nombre_nuevo,)
            )
            fila = cursor.fetchone()
            if not fila:
                cursor.execute("INSERT INTO usuarios (nombre) VALUES (?)", (nombre_nuevo,))
                conn.commit()
        conn.close()
        return RedirectResponse("/admin/usuarios", status_code=303)

    # Renombrar un usuario (formulario de cada fila)
    if renombrar_id and nuevo_nombre:
        nuevo_nombre = nuevo_nombre.strip()
        if nuevo_nombre:
            cursor.execute(
                "SELECT id FROM usuarios WHERE LOWER(nombre) = LOWER(?)", (nuevo_nombre,)
            )
            fila = cursor.fetchone()
            if not fila or fila["id"] == renombrar_id:
                cursor.execute(
                    "UPDATE usuarios SET nombre = ? WHERE id = ?",
                    (nuevo_nombre, renombrar_id),
                )
                conn.commit()
        conn.close()
        return RedirectResponse("/admin/usuarios", status_code=303)

    cursor.execute(
        """
        SELECT u.id, u.nombre,
               COUNT(p.id) AS partidas,
               IFNULL(SUM(p.aciertos), 0) AS aciertos
        FROM usuarios u
        LEFT JOIN partidas p ON p.usuario_id = u.id
        GROUP BY u.id
        ORDER BY u.nombre
        """
    )
    usuarios = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return templates.TemplateResponse(
        request, name="admin_usuarios.html", context={"usuarios": usuarios}
    )


@app.get("/admin/usuarios/{usuario_id}/eliminar")
def admin_eliminar_usuario(usuario_id: int):
    """Admin — elimina un usuario junto con sus partidas."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM partidas WHERE usuario_id = ?", (usuario_id,))
    cursor.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/usuarios", status_code=303)


@app.get("/admin/trivias-usuarios")
def admin_trivias_usuarios(request: Request):
    """Admin — partidas de cada usuario agrupadas por usuario."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.nombre AS usuario,
               p.aciertos, p.total, p.fecha,
               CASE WHEN p.trivia_id IS NULL THEN 'Todas las trivias' ELSE t.pregunta END AS trivia
        FROM partidas p
        JOIN usuarios u ON p.usuario_id = u.id
        LEFT JOIN trivia t ON p.trivia_id = t.id
        ORDER BY u.nombre, p.id
        """
    )
    # Agrupamos las partidas por usuario para mostrarlas en tablas separadas
    por_usuario = []
    for fila in cursor.fetchall():
        datos = dict(fila)
        if not por_usuario or por_usuario[-1]["usuario"] != datos["usuario"]:
            por_usuario.append({"usuario": datos["usuario"], "partidas": []})
        por_usuario[-1]["partidas"].append(datos)
    conn.close()

    return templates.TemplateResponse(
        request, name="admin_trivias_usuarios.html", context={"por_usuario": por_usuario}
    )


if __name__ == "__main__":
    import uvicorn

    inicializar_db()
    uvicorn.run(app, host="127.0.0.1", port=8000)


