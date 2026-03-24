"""Palantir AIP Ontology Demo - Entry Point.

This is the main entry point for backward compatibility.
The application has been refactored into a modular structure under the app/ directory.

Run with:
    streamlit run app.py

Or use the new entry point:
    streamlit run app/main.py
"""

from app.ui import render_main_page

if __name__ == '__main__':
    render_main_page()
