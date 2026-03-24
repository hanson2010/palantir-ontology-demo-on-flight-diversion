"""Main entry point for the Streamlit application.

Run this module to start the Streamlit app:
    streamlit run app/main.py
"""

from .ui import render_main_page

if __name__ == '__main__':
    render_main_page()
