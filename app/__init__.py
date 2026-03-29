"""Palantir Ontology Demo Application.

This package provides a flight diversion demonstration using:
- Neo4j for ontology data storage
- LangChain/OpenAI for LLM reasoning
- Streamlit for the user interface
"""

from .config import neo4j_driver, llm
from .database import get_ontology_data
from .services import get_passenger_summary, execute_action
from .llm import invoke_llm_with_retry

__version__ = '1.0.0'
__all__ = [
    'neo4j_driver',
    'llm',
    'get_ontology_data',
    'get_passenger_summary',
    'execute_action',
    'invoke_llm_with_retry',
]
