#eventapp/index.py
#Entry point for running the application
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from eventapp import app

if __name__ == '__main__':
    app.run(debug=True)