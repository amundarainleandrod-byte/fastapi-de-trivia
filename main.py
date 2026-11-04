import sqlite3
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
    trivia_pregunta: str = "",
):
    """Muestra el formulario y, si llegan datos, guarda la pregunta."""
    if not pregunta or not respuesta or not trivia_pregunta:
        # Primera visita: solo mostramos el formulario vacío
        return templates.TemplateResponse(request, name="crear.html", context={})

    conn = conectar_db()
    cursor = conn.cursor()
    trivia_id = obtener_o_crear_trivia(cursor, conn, trivia_pregunta)
    cursor.execute(
        "INSERT INTO questions (pregunta, respuesta, trivia_id) VALUES (?, ?, ?)",
        (pregunta, respuesta, trivia_id),
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
    nueva_genero: str = "",
):
    """Muestra el formulario con los valores actuales y guarda los cambios."""
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

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")

    pregunta_actual = row["pregunta"]
    respuesta_actual = row["respuesta"]
    genero_actual = row["trivia"] or ""

    # Primera visita: solo mostramos el formulario con los valores actuales
    if not nuevo_pregunta and not nuevo_respuesta and not nueva_genero:
        conn.close()
        return templates.TemplateResponse(
            request,
            name="editar.html",
            context={"q": dict(row)},
        )

    # Si un campo llega vacío, conservamos el valor actual
    if not nuevo_pregunta:
        nuevo_pregunta = pregunta_actual
    if not nuevo_respuesta:
        nuevo_respuesta = respuesta_actual
    if not nueva_genero:
        nueva_genero = genero_actual

    trivia_id = obtener_o_crear_trivia(cursor, conn, nueva_genero)
    cursor.execute(
        "UPDATE questions SET pregunta = ?, respuesta = ?, trivia_id = ? WHERE id = ?",
        (nuevo_pregunta, nuevo_respuesta, trivia_id, game_id),
    )
    conn.commit()
    conn.close()

    # Volvemos al detalle de la pregunta editada
    return RedirectResponse(f"/questions/{game_id}", status_code=303)


@app.get("/questions/{game_id}/eliminar")
def eliminar_game(game_id: int):
    """Elimina una pregunta y vuelve al inicio."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE id = ?", (game_id,))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)


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
def jugar(request: Request, genero: str = "", todas: str = "", pos: int = 0, aciertos: int = 0):
    """Vista para jugar la trivia: muestra una pregunta por vez."""
    conn = conectar_db()
    cursor = conn.cursor()

    jugando = bool(genero) or todas == "1"
    questions = []
    generos = []
    genero_encontrado = True

    if jugando:
        if todas == "1":
            cursor.execute("SELECT h.id, h.pregunta FROM questions h ORDER BY h.id")
            questions = [dict(fila) for fila in cursor.fetchall()]
        else:
            cursor.execute(
                "SELECT id FROM trivia WHERE LOWER(pregunta) = LOWER(?)", (genero,)
            )
            fila = cursor.fetchone()
            if fila:
                cursor.execute(
                    "SELECT id, pregunta FROM questions WHERE trivia_id = ? ORDER BY id",
                    (fila["id"],),
                )
                questions = [dict(cada) for cada in cursor.fetchall()]
            else:
                genero_encontrado = False
    else:
        # Menú de juego: mostramos los géneros disponibles
        cursor.execute("SELECT pregunta FROM trivia ORDER BY pregunta")
        generos = [fila["pregunta"] for fila in cursor.fetchall()]

    conn.close()

    total = len(questions)
    terminado = jugando and pos >= total
    pregunta_actual = questions[pos] if jugando and not terminado else None

    return templates.TemplateResponse(
        request,
        name="jugar.html",
        context={
            "jugando": jugando,
            "terminado": terminado,
            "genero": genero,
            "todas": todas,
            "pos": pos,
            "aciertos": aciertos,
            "total": total,
            "pregunta": pregunta_actual,
            "generos": generos,
            "genero_encontrado": genero_encontrado,
        },
    )


@app.get("/jugar/responder")
def responder_pregunta(
    request: Request,
    pregunta_id: int,
    respuesta: str = "",
    pos: int = 0,
    genero: str = "",
    todas: str = "",
    aciertos: int = 0,
):
    """Comprueba la respuesta del jugador y prepara la siguiente pregunta."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT respuesta FROM questions WHERE id = ?", (pregunta_id,))
    fila = cursor.fetchone()
    conn.close()

    if not fila:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")

    respuesta_jugador = respuesta.strip()
    respuesta_correcta = fila["respuesta"].strip()
    correcta = respuesta_jugador.lower() == respuesta_correcta.lower()

    if correcta:
        aciertos += 1
    pos += 1

    # Enlace para continuar jugando con la pregunta siguiente (lleva el marcador)
    params = {"pos": pos, "aciertos": aciertos}
    if genero:
        params["genero"] = genero
    if todas == "1":
        params["todas"] = todas
    siguiente_url = "/jugar?" + urlencode(params)

    return templates.TemplateResponse(
        request,
        name="resultado.html",
        context={
            "correcta": correcta,
            "respuesta_jugador": respuesta_jugador,
            "respuesta_correcta": respuesta_correcta,
            "siguiente_url": siguiente_url,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


inicializar_db()
