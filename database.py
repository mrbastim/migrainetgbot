import sqlite3

def init_db():
    """Initializes the database and creates the notes table if it doesn't exist."""
    conn = sqlite3.connect('notes.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_note(user_id, text):
    """Adds a note to the database for a given user."""
    conn = sqlite3.connect('notes.db')
    cur = conn.cursor()
    cur.execute("INSERT INTO notes (user_id, text) VALUES (?, ?)", (user_id, text))
    conn.commit()
    conn.close()

def get_notes(user_id):
    """Retrieves all notes for a given user."""
    conn = sqlite3.connect('notes.db')
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM notes WHERE user_id = ?", (user_id,))
    notes = cur.fetchall()
    conn.close()
    return notes

def delete_note(note_id):
    """Deletes a note by its ID."""
    conn = sqlite3.connect('notes.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()
