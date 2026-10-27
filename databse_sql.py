import sqlite3

DATABASE_pregunta = "questions.db"


def conectar_db():
    conn = sqlite3.connect(DATABASE_pregunta)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def inicializar_db(conn):
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


def obtener_o_crear_trivia(cursor, conn, trivia_pregunta):
    cursor.execute("SELECT id FROM trivia WHERE pregunta = ?", (trivia_pregunta,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO trivia (pregunta) VALUES (?)", (trivia_pregunta,))
    conn.commit()
    return cursor.lastrowid


def crear_game(conn):
    cursor = conn.cursor()
    print("\n--- Crear Trivia ---")
    pregunta = input("Introduzca la pregunta: ").strip()
    respuesta = input("Introduzca la respuesta: ").strip()
    trivia_pregunta = input("Genero de la trivia ").strip()

    if not pregunta or not respuesta or not trivia_pregunta:
        print("Error: Todos los campos son obligatorios.")
        return

    trivia_id = obtener_o_crear_trivia(cursor, conn, trivia_pregunta)
    cursor.execute(
        "INSERT INTO questions (pregunta, respuesta, trivia_id) VALUES (?, ?, ?)",
        (pregunta, respuesta, trivia_id),
    )
    conn.commit()
    print(f"Trivia '{pregunta}' creada con éxito (ID: {cursor.lastrowid}).")


def listar_questions(conn):
    cursor = conn.cursor()
    print("\n--- Listado de Trivia ---")
    query = """
    SELECT h.id, h.pregunta, h.respuesta, f.pregunta
    FROM questions h
    LEFT JOIN trivia f ON h.trivia_id = f.id
    """
    cursor.execute(query)
    questions = cursor.fetchall()

    if not questions:
        print("No hay nada registrado.")
        return

    for game_id, pregunta, respuesta, trivia in questions:
        print(f"ID: {game_id} | Pregunta: {pregunta} | Respuesta: {respuesta} | Genero: {trivia}")


def buscar_trivia(conn):
    cursor = conn.cursor()
    print("\n--- Buscar  ---")
    busqueda = input("Ingresa el nombre o ID de la trivia: ").strip()
    if not busqueda:
        print("Búsqueda cancelada.")
        return

    if busqueda.isdigit():
        query = """
        SELECT h.id, h.pregunta, h.respuesta, f.pregunta
        FROM questions h
        LEFT JOIN trivia f ON h.trivia_id = f.id
        WHERE h.id = ?
        """
        cursor.execute(query, (int(busqueda),))
    else:
        query = """
        SELECT h.id, h.pregunta, h.respuesta, f.pregunta
        FROM questions h
        LEFT JOIN trivia f ON h.trivia_id = f.id
        WHERE LOWER(h.pregunta) LIKE ?
        """
        cursor.execute(query, (f"%{busqueda.lower()}%",))

    questions = cursor.fetchall()
    if not questions:
        print("No se encontraron resultados.")
        return

    for game_id, pregunta, respuesta, trivia in questions:
        print(f"ID: {game_id} | Pregunta: {pregunta} | Respuesta: {respuesta} | Genero: {trivia}")


def actualizar_game(conn):
    cursor = conn.cursor()
    print("\n--- Actualizar Trivia ---")
    game_id_input = input("Ingresa el ID del Trivia a actualizar: ").strip()
    if not game_id_input.isdigit():
        print("ID inválido.")
        return

    game_id = int(game_id_input)
    cursor.execute(
        """
        SELECT h.pregunta, h.respuesta, f.pregunta
        FROM questions h
        LEFT JOIN trivia f ON h.trivia_id = f.id
        WHERE h.id = ?
        """,
        (game_id,),
    )
    game = cursor.fetchone()
    if not game:
        print("Trivia no encontrado.")
        return

    pregunta_actual, respuesta_actual, genero_actual = game
    print(f"Valores actuales -> Pregunta: {Pregunta_actual} | Respuesta: {Respuesta_actual} | Genero: {Genero_actual}")

    nuevo_pregunta = input("Nuevo Pregunta (Enter para conservar): ").strip() or Pregunta_actual
    nuevo_respuesta = input("Nuevo Respuesta (Enter para conservar): ").strip() or Respuesta_actual
    nueva_Genero = input("Nueva Genero (Enter para conservar): ").strip() or Genero_actual

    trivia_id = obtener_o_crear_Genero(cursor, conn, nueva_Genero)

    cursor.execute(
        "UPDATE questions SET pregunta = ?, respuesta = ?, trivia_id = ? WHERE id = ?",
        (nuevo_Pregunta, nuevo_Respuesta, trivia_id, game_id),
    )
    conn.commit()
    print("Trivia actualizado correctamente.")


def eliminar_game(conn):
    cursor = conn.cursor()
    print("\n--- Eliminar Trivia ---")
    game_id_input = input("Ingresa el ID del Trivia a eliminar: ").strip()
    if not game_id_input.isdigit():
        print("ID inválido.")
        return

    game_id = int(game_id_input)
    cursor.execute("DELETE FROM questions WHERE id = ?", (game_id,))
    conn.commit()

    if cursor.rowcount > 0:
        print(f"Trivia con ID {game_id} eliminado exitosamente.")
    else:
        print("Trivia no encontrado.")


def obtener_questions_Genero(conn, trivia_pregunta=None):
    cursor = conn.cursor()
    if trivia_pregunta is None:
        print("\n--- Trivias por Genero ---")
        trivia_pregunta = input("Pregunta de la Genero: ").strip()

    if not trivia_pregunta:
        print("Pregunta de Genero no proporcionado.")
        return []

    cursor.execute("SELECT id FROM trivia WHERE LOWER(pregunta) = LOWER(?)", (trivia_pregunta,))
    row = cursor.fetchone()
    if not row:
        print(f"No se encontró la Genero '{trivia_pregunta}'.")
        return []

    trivia_id = row[0]
    cursor.execute(
        "SELECT id, pregunta, respuesta FROM questions WHERE trivia_id = ?",
        (trivia_id,),
    )
    questions_trivia = cursor.fetchall()

    if not questions_trivia:
        print(f"No hay Trivias registrados para el Genero '{trivia_pregunta}'.")
    else:
        print(f"\n--- Trivias de '{trivia_pregunta}' ---")
        for game_id, pregunta, respuesta in questions_trivia:
            print(f"ID: {game_id} | Pregunta: {pregunta} | Respuesta: {respuesta}")

    return questions_trivia


def main():
    conn = conectar_db()
    inicializar_db(conn)

    while True:
        print("\n==============================")
        print("       CRUD DE Trivias")
        print("==============================")
        print("1. Crear Trivia")
        print("2. Listar Trivias")
        print("3. Buscar Trivia")
        print("4. Actualizar Trivia")
        print("5. Eliminar Trivia")
        print("6. Listar Trivias por Genero")
        print("7. Salir")

        opcion = input("\nSelecciona una opción (1-7): ").strip()

        if opcion == "1":
            crear_game(conn)
        elif opcion == "2":
            listar_questions(conn)
        elif opcion == "3":
            buscar_game(conn)
        elif opcion == "4":
            actualizar_game(conn)
        elif opcion == "5":
            eliminar_game(conn)
        elif opcion == "6":
            obtener_questions_Genero(conn)
        elif opcion == "7":
            print("\nCerrando conexión y saliendo del programa...")
            break
        else:
            print("Opción no válida. Intenta nuevamente.")

    conn.close()


if __name__ == "__main__":
    main()
