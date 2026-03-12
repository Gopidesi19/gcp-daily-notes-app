
import os
import datetime
from flask import Flask, render_template, request, redirect, url_for
from google.cloud import firestore

# --- Configuration ---
# GCP Project ID is read from the environment variable.
PROJECT_ID = os.environ.get('GCP_PROJECT', None)
if not PROJECT_ID:
    raise ValueError("GCP_PROJECT environment variable not set.")

# Initialize Firestore DB client
db = firestore.Client(project=PROJECT_ID)
NOTES_COLLECTION = "notes"
APP_VERSION = "1.0.0"

app = Flask(__name__)

# --- Routes ---

@app.route('/')
def index():
    """
    Main route to display the notes UI.
    Fetches all notes from Firestore and renders them in the template.
    """
    try:
        # Fetch notes from Firestore, ordered by timestamp descending
        notes_stream = db.collection(NOTES_COLLECTION).order_by(
            'timestamp', direction=firestore.Query.DESCENDING
        ).stream()

        # Format notes for display
        notes = [note.to_dict() for note in notes_stream]

    except Exception as e:
        print(f"Error fetching notes: {e}")
        notes = []

    return render_template('index.html', notes=notes, app_version=APP_VERSION)


@app.route('/add', methods=['POST'])
def add_note():
    """
    Route to add a new note to the database.
    Accepts a POST request with the note content.
    """
    note_text = request.form.get('note')

    if not note_text:
        # Redirect back if the note is empty
        return redirect(url_for('index'))

    try:
        # Create the note document data
        note_data = {
            'note': note_text,
            'timestamp': datetime.datetime.now(tz=datetime.timezone.utc),
            'version': APP_VERSION
        }

        # Add a new document to the 'notes' collection with an auto-generated ID
        db.collection(NOTES_COLLECTION).add(note_data)

    except Exception as e:
        print(f"Error adding note: {e}")

    # Redirect back to the main page to see the new note
    return redirect(url_for('index'))


# --- Main ---

if __name__ == '__main__':
    # This is used for local development.
    # When deployed on Cloud Run, a production-grade WSGI server like Gunicorn is used.
    app.run(host='127.0.0.1', port=8080, debug=True)
