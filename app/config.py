"""Configuration and initialization module.

This module handles loading environment variables and initializing
external service connections (Neo4j, LLM).
"""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

# Neo4j connection
neo4j_driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)

# LLM configuration
llm = ChatOpenAI(
    base_url=os.getenv('OPENAI_BASE_URL'),
    api_key=os.getenv('OPENAI_API_KEY'),
    model=os.getenv('MODEL_ID'),
    temperature=0
)
