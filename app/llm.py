"""LLM utilities and prompts module.

This module contains LLM invocation utilities and prompt templates
for the AIP reasoning logic.
"""

import time
import streamlit as st

from .config import llm


def invoke_llm_with_retry(prompt, max_retries: int = 3, delay: int = 2):
    """Invoke LLM with retry mechanism for handling transient errors.

    Args:
        prompt: The prompt to send to the LLM.
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries (uses exponential backoff).

    Returns:
        The LLM response.

    Raises:
        ValueError: If all retries fail or non-retryable error occurs.
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return llm.invoke(prompt)
        except ValueError as e:
            last_error = e
            if '502' in str(e) or 'Provider returned error' in str(e):
                if attempt < max_retries - 1:
                    st.warning(f"API 暂时不可用，正在重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
            else:
                raise e
    raise last_error


# Prompt template for flight diversion event
DIVERSION_PROMPT_TEMPLATE = '''
You are the reasoning core of Palantir AIP. A flight diversion event has occurred.
You need to analyze the current state of the Ontology (provided below) and generate a JSON list of Actions to execute in the system.

Ontology Data:
{ontology_data}

Passenger Summary for Ground Service:
{passenger_summary}

Rules:
1. Gold Passengers get 5-star hotels if available.
2. Regular Passengers get 3-star hotels.
3. Generate NotifyGroundService action with detailed passenger summary including:
   - Total passenger count
   - Gold/Regular passenger counts and names
   - Hotel requirements (5-star vs 3-star room counts)
   - Any terminated passengers
4. Exclude terminated passengers from hotel bookings.
5. You MUST generate ALL of the following action types: SetFlightStatus, NotifyGroundService, BookHotel (for each passenger), UpdateHotelInventory.

Expected Action JSON Schema (List of Actions):
[
    {{ "type": "SetFlightStatus", "params": {{ "iata": "string", "status": "Diverted" }} }},
    {{ "type": "NotifyGroundService", "params": {{ "summary": {{ "total": number, "gold": number, "regular": number, "hotelNeeds": {{ "5star": number, "3star": number }} }}, "message": "string" }} }},
    {{ "type": "BookHotel", "params": {{ "passengerId": "string", "hotelName": "string" }} }},
    {{ "type": "UpdateHotelInventory", "params": {{ "name": "string" }} }}
]

Example output for a flight with 2 passengers (1 Gold, 1 Regular):
[
    {{ "type": "SetFlightStatus", "params": {{ "iata": "CA123", "status": "Diverted" }} }},
    {{ "type": "NotifyGroundService", "params": {{ "summary": {{ "total": 2, "gold": 1, "regular": 1, "hotelNeeds": {{ "5star": 1, "3star": 1 }} }}, "message": "Flight CA123 diverted to SZX. Please arrange ground transportation and accommodation." }} }},
    {{ "type": "BookHotel", "params": {{ "passengerId": "P001", "hotelName": "Hyatt Airport" }} }},
    {{ "type": "BookHotel", "params": {{ "passengerId": "P002", "hotelName": "Comfort Inn" }} }},
    {{ "type": "UpdateHotelInventory", "params": {{ "name": "Hyatt Airport" }} }},
    {{ "type": "UpdateHotelInventory", "params": {{ "name": "Comfort Inn" }} }}
]

Generate ONLY the JSON array, no other text.
'''


# Prompt template for sub-flight (recovery flight) creation
SUBFLIGHT_PROMPT_TEMPLATE = '''
You are the reasoning core of Palantir AIP. A sub-flight (recovery flight) needs to be created.
You need to analyze the current state of the Ontology and generate Actions to create the sub-flight.

Ontology Data:
{ontology_data}

Rules:
1. Create a sub-flight with IATA code based on main flight (e.g., AC123 -> AC123A).
2. Schedule the sub-flight for the next day at 08:00 local time.
3. Only include passengers who have NOT terminated their journey.
4. Notify ground service about the sub-flight creation with passenger list.

Expected Action JSON Schema (List of Actions):
[
    {{ "type": "CreateSubFlight", "params": {{ "mainFlight": "string", "subFlightIata": "string", "scheduledTime": "string" }} }},
    {{ "type": "NotifyGroundService", "params": {{ "message": "string", "subFlightDetails": {{ "iata": "string", "time": "string", "passengerCount": number }} }} }}
]

Generate ONLY the JSON array, no other text.
'''
