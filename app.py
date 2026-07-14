"""
Root-level app.py for gunicorn compatibility.
This allows 'gunicorn app:app' to work correctly.
"""
from wsgi import app

if __name__ == "__main__":
    app.run()
