"""Main page layout module.

This module contains the main page layout and event handlers for the
Streamlit application.

Function Organization:
1. Session State Management
2. Event Handlers (Reset, Diversion, Subflight, Termination)
3. Panel Render Functions
4. Main Page Entry Point
"""

import json

import streamlit as st

from ..database import get_ontology_data, get_flight_status, get_system_status, reset_database
from ..llm import (
    invoke_llm_with_retry,
    DIVERSION_PROMPT_TEMPLATE,
    SUBFLIGHT_PROMPT_TEMPLATE
)
from ..services import (
    get_passenger_summary,
    execute_action,
    execute_terminate_passengers
)
from .components import (
    render_header,
    render_foundry_status_summary,
    render_flight_status,
    render_ground_service_panel,
    render_hotel_panel,
    render_passenger_panel,
    render_termination_section,
    render_debug_section
)


# =============================================================================
# Session State Management
# =============================================================================

def init_session_state():
    """Initialize Streamlit session state variables."""
    if 'foundry_actions' not in st.session_state:
        st.session_state['foundry_actions'] = []
    if 'diversion_triggered' not in st.session_state:
        st.session_state['diversion_triggered'] = False
    if 'terminated_passengers' not in st.session_state:
        st.session_state['terminated_passengers'] = []
    if 'is_reasoning' not in st.session_state:
        st.session_state['is_reasoning'] = False
    if 'pending_diversion' not in st.session_state:
        st.session_state['pending_diversion'] = None
    if 'pending_subflight' not in st.session_state:
        st.session_state['pending_subflight'] = None


# =============================================================================
# Event Handlers
# =============================================================================

def handle_reset():
    """Handle the reset button click to restore initial database state."""
    reset_database()
    st.session_state['foundry_actions'] = []
    st.session_state['diversion_triggered'] = False
    st.session_state['terminated_passengers'] = []
    st.session_state['is_reasoning'] = False
    st.session_state['pending_diversion'] = None
    st.session_state['pending_subflight'] = None
    st.session_state['llm_raw_response'] = None
    st.success('✅ 数据已重置')
    st.rerun()


def start_diversion_event(flight_iata: str, alternate_iata: str):
    """Start the diversion event - sets pending state and triggers rerun."""
    st.session_state['pending_diversion'] = (flight_iata, alternate_iata)
    st.session_state['is_reasoning'] = True
    st.rerun()


def execute_diversion_event(flight_iata: str, alternate_iata: str):
    """Execute the flight diversion event (called after rerun when is_reasoning is True).

    This function:
    1. Retrieves ontology data from Neo4j
    2. Calls the LLM for reasoning
    3. Executes the generated actions

    Args:
        flight_iata: The IATA code of the flight.
        alternate_iata: The IATA code of the alternate airport.
    """
    # Step 1: Retrieve data from Neo4j AuraDB
    ontology_data = get_ontology_data(flight_iata, alternate_iata)
    passenger_summary = get_passenger_summary(ontology_data['passengers'])

    # Step 2: Call OpenAI for reasoning
    final_prompt = DIVERSION_PROMPT_TEMPLATE.format(
        ontology_data=json.dumps(ontology_data, ensure_ascii=False),
        passenger_summary=json.dumps(passenger_summary, ensure_ascii=False)
    )
    response = invoke_llm_with_retry(final_prompt)

    # DEBUG: Store LLM raw response
    st.session_state['llm_raw_response'] = response.content

    # Step 3: Synchronize Neo4j state
    executed_actions = execute_action(response.content)
    st.session_state['foundry_actions'] = executed_actions
    st.session_state['diversion_triggered'] = True
    st.session_state['is_reasoning'] = False
    st.session_state['pending_diversion'] = None
    st.rerun()


def start_subflight_creation(flight_iata: str, alternate_iata: str):
    """Start the subflight creation - sets pending state and triggers rerun."""
    st.session_state['pending_subflight'] = (flight_iata, alternate_iata)
    st.session_state['is_reasoning'] = True
    st.rerun()


def execute_subflight_creation(flight_iata: str, alternate_iata: str):
    """Execute the sub-flight (recovery flight) creation (called after rerun).

    Args:
        flight_iata: The IATA code of the main flight.
        alternate_iata: The IATA code of the alternate airport.
    """
    ontology_data = get_ontology_data(flight_iata, alternate_iata)

    final_prompt = SUBFLIGHT_PROMPT_TEMPLATE.format(
        ontology_data=json.dumps(ontology_data, ensure_ascii=False)
    )
    response = invoke_llm_with_retry(final_prompt)

    executed_actions = execute_action(response.content)
    st.session_state['foundry_actions'] = st.session_state['foundry_actions'] + executed_actions
    st.session_state['is_reasoning'] = False
    st.session_state['pending_subflight'] = None
    st.rerun()


def handle_passenger_termination(passenger_ids: list):
    """Handle passenger journey termination.

    Args:
        passenger_ids: List of passenger IDs to terminate.
    """
    execute_terminate_passengers(passenger_ids)
    st.session_state['terminated_passengers'] = (
        st.session_state.get('terminated_passengers', []) + passenger_ids
    )
    st.success(f"已终止 {len(passenger_ids)} 位旅客的行程")
    st.rerun()


# =============================================================================
# Panel Render Functions
# =============================================================================

def render_occ_panel(flight_iata: str, alternate_iata: str, actions: list):
    """Render the OCC (Operations Control Center) panel.

    Args:
        flight_iata: The IATA code of the selected flight.
        alternate_iata: The IATA code of the selected alternate airport.
        actions: List of executed actions.
    """
    st.header('🏢 航司/OCC')

    # Get initial flight status from database
    try:
        initial_flight_data = get_flight_status(flight_iata)
    except Exception:
        initial_flight_data = {'iata': flight_iata, 'status': 'Unknown'}

    # Display flight status
    render_flight_status(actions, flight_iata, initial_flight_data)

    # OCC Control Panel
    st.subheader('控制面板')
    flight_to_divert = st.selectbox('选择航班', ['CA123'], key='flight_select')
    alternate_airport = st.selectbox('选择备降场', ['SZX'], key='airport_select')

    # Diversion event button
    if st.button('🚨 发起备降事件', key='trigger'):
        start_diversion_event(flight_to_divert, alternate_airport)

    # Sub-flight preparation button
    if st.session_state.get('diversion_triggered'):
        if st.button('🛫 准备补班航班', key='subflight'):
            start_subflight_creation(flight_to_divert, alternate_airport)


# =============================================================================
# Main Page Entry Point
# =============================================================================

def render_main_page():
    """Render the main application page.

    This is the entry point for the Streamlit UI.
    """
    st.set_page_config(layout='wide', page_title='Palantir Ontology 演示')

    # Initialize session state
    init_session_state()

    # Render header
    render_header()

    # Get system status and render Foundry status summary
    try:
        system_status = get_system_status()
    except Exception:
        system_status = {'flights': 0, 'passengers': 0, 'hotels': 0, 'subFlights': 0}

    # Check if we need to execute pending operations
    is_reasoning = st.session_state.get('is_reasoning', False)
    pending_diversion = st.session_state.get('pending_diversion')
    pending_subflight = st.session_state.get('pending_subflight')

    # Render Foundry status summary with reasoning indicator
    render_foundry_status_summary(
        system_status=system_status,
        on_reset_callback=handle_reset,
        is_reasoning=is_reasoning
    )

    # Execute pending operations after status bar is rendered
    if pending_diversion:
        execute_diversion_event(pending_diversion[0], pending_diversion[1])
    elif pending_subflight:
        execute_subflight_creation(pending_subflight[0], pending_subflight[1])

    # Four-column layout
    col1, col2, col3, col4 = st.columns(4)

    actions = st.session_state.get('foundry_actions', [])
    flight_iata = st.session_state.get('flight_select', 'CA123')
    alternate_iata = st.session_state.get('airport_select', 'SZX')

    # Column 1: OCC (Operations Control Center)
    with col1:
        render_occ_panel(flight_iata, alternate_iata, actions)

    # Column 2: Ground Service / DCS
    with col2:
        render_ground_service_panel(actions)

    # Column 3: Hotels
    with col3:
        render_hotel_panel(actions)

    # Column 4: Passengers
    with col4:
        st.header('📱 旅客')

        # Passenger termination section (only after diversion triggered)
        if st.session_state.get('diversion_triggered'):
            render_termination_section(
                flight_iata=flight_iata,
                alternate_iata=alternate_iata,
                get_ontology_data_func=get_ontology_data,
                on_terminate_callback=handle_passenger_termination
            )

        # Passenger panel with hotel bookings
        render_passenger_panel(
            actions=actions,
            terminated_passengers=st.session_state.get('terminated_passengers', [])
        )

    # Debug section
    render_debug_section(
        llm_raw_response=st.session_state.get('llm_raw_response'),
        foundry_actions=st.session_state.get('foundry_actions')
    )
