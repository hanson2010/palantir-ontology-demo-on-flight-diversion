"""Reusable UI components module.

This module contains reusable Streamlit UI components for rendering
different sections of the application.

Function Organization:
1. Header Components
2. Status Summary Components
3. Panel Components (OCC, Ground Service, Hotel, Passenger)
4. Debug Components
"""

import streamlit as st


# =============================================================================
# Header Components
# =============================================================================

def render_header():
    """Render the application header with title and description."""
    st.markdown("""
    <div style="text-align: center;">
        <h1>✈️ Palantir AIP 本体论演示</h1>
        <p>本体论（Data）+ 大模型（Reasoning）+ 动作框架（Action Execution）的无缝闭环</p>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# Status Summary Components
# =============================================================================

def render_aip_status_summary(system_status: dict, on_reset_callback, is_reasoning: bool = False):
    """Render the AIP status summary bar.

    Args:
        system_status: Dictionary containing system status (flights, passengers, hotels, subFlights).
        on_reset_callback: Callback function to reset the database.
        is_reasoning: Whether the system is currently reasoning.
    """
    # Add CSS for compact vertical centering
    st.markdown("""
    <style>
        div[data-testid="stMetric"] {
            background-color: transparent;
            border: none;
            padding: 0;
        }
        div[data-testid="stMetric"] > label {
            font-size: 0.85rem;
        }
        div[data-testid="stMetric"] > div {
            font-size: 1.2rem;
        }
    </style>
    """, unsafe_allow_html=True)

    # Status indicators in a single row
    col1, col2, col3, col4, col5, col6 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5, 1])

    with col1:
        st.metric("✈️ 航班", system_status.get('flights', 0))
    with col2:
        st.metric("👥 旅客", system_status.get('passengers', 0))
    with col3:
        st.metric("🏨 酒店", system_status.get('hotels', 0))
    with col4:
        st.metric("🛫 补班", system_status.get('subFlights', 0))
    with col5:
        if is_reasoning:
            st.markdown("""
            <div style="display: flex; align-items: center; padding-top: 1.5rem;">
                <span style="
                    width: 20px;
                    height: 20px;
                    border: 2px solid #f3f3f3;
                    border-top: 2px solid #3498db;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                "></span>
                <span style="margin-left: 8px; color: #3498db; font-weight: bold;">推理中...</span>
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
            """, unsafe_allow_html=True)
    with col6:
        if st.button("🔄 重置数据", key="reset_btn", type="secondary"):
            on_reset_callback()

    st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)


def render_flight_status(actions: list, flight_iata: str, initial_flight_data: dict = None):
    """Render flight status section.

    Args:
        actions: List of executed actions.
        flight_iata: The IATA code of the selected flight.
        initial_flight_data: Initial flight data from database (before any actions).
    """
    st.subheader('航班状态')

    # Check if there's a SetFlightStatus action for this flight
    status_action = None
    for act in actions:
        if act['type'] == 'SetFlightStatus' and act['params'].get('iata') == flight_iata:
            status_action = act
            break

    # Display flight status - either from action or initial data (always UPPERCASED)
    if status_action:
        status = status_action['params']['status'].upper()
        st.info(f"✈️ 航班 {status_action['params']['iata']} 状态: **{status}**")
    elif initial_flight_data:
        status = initial_flight_data.get('status', 'Unknown').upper()
        st.info(f"✈️ 航班 {flight_iata} 状态: **{status}**")

    # Display sub-flight creation
    for act in actions:
        if act['type'] == 'CreateSubFlight':
            params = act['params']
            st.success(f"🛫 补班航班 **{params['subFlightIata']}**\n\n计划时间: {params['scheduledTime']}")


# =============================================================================
# Panel Components
# =============================================================================

def render_ground_service_panel(actions: list):
    """Render the ground service (DCS) panel.

    Args:
        actions: List of executed actions.
    """
    st.header('🛂 机场地服/DCS')
    for act in actions:
        if act['type'] == 'NotifyGroundService':
            if 'summary' in act['params']:
                summary = act['params']['summary']
                st.warning(f"📋 **乘客摘要**")
                st.markdown(f"""
                - 总乘客数: **{summary.get('total', 'N/A')}**
                - 金卡乘客: {summary.get('gold', 0)} 位
                - 普通乘客: {summary.get('regular', 0)} 位
                - 酒店需求: 5星 {summary.get('hotelNeeds', {}).get('5star', 0)} 间 / 3星 {summary.get('hotelNeeds', {}).get('3star', 0)} 间
                """)
                if act['params'].get('message'):
                    st.info(f"💬 {act['params']['message']}")
            elif 'subFlightDetails' in act['params']:
                details = act['params']['subFlightDetails']
                st.success(f"🛫 **补班航班通知**")
                st.markdown(f"""
                - 航班号: **{details['iata']}**
                - 计划时间: {details['time']}
                - 乘客数: {details['passengerCount']} 位
                """)
                if act['params'].get('message'):
                    st.info(f"💬 {act['params']['message']}")
            else:
                st.warning(f"指令下发：{act['params'].get('msg', act['params'])}")


def render_hotel_panel(actions: list):
    """Render the hotel panel showing booked hotels.

    Args:
        actions: List of executed actions.
    """
    st.header('🏨 协议酒店')

    # Get all hotel booking actions
    hotel_bookings = [act for act in actions if act['type'] == 'BookHotel']

    if hotel_bookings:
        # Show aggregate hotel names
        booked_hotels = list(set([act['params']['hotelName'] for act in hotel_bookings]))
        st.success(f"AIP 自动预订确认：\n\n{', '.join(booked_hotels)}")

        # Show passenger-hotel mapping
        st.markdown("### 📋 预订明细")
        for act in hotel_bookings:
            st.markdown(f"- **{act['params']['passengerId']}**: {act['params']['hotelName']}")


def render_passenger_panel(actions: list, terminated_passengers: list):
    """Render the passenger panel with termination status.

    Args:
        actions: List of executed actions.
        terminated_passengers: List of terminated passenger IDs.
    """
    # Display terminated passengers
    if terminated_passengers:
        st.markdown("### ⛔ 已终止行程")
        for p in terminated_passengers:
            st.markdown(f"- {p} (已终止)")
    else:
        st.info("暂无旅客状态更新")


def render_termination_section(
    flight_iata: str,
    alternate_iata: str,
    get_ontology_data_func,
    on_terminate_callback
):
    """Render the passenger journey termination section.

    Args:
        flight_iata: The IATA code of the flight.
        alternate_iata: The IATA code of the alternate airport.
        get_ontology_data_func: Function to retrieve ontology data.
        on_terminate_callback: Callback function when termination is confirmed.
    """
    st.markdown("### 🚫 自愿终止行程")
    st.markdown("*旅客可选择终止行程，将不会被安排补班航班*")

    try:
        ontology_data = get_ontology_data_func(flight_iata, alternate_iata)
        passengers = ontology_data.get('passengers', [])
        active_passengers = [p for p in passengers if not p.get('terminated')]

        if active_passengers:
            passenger_options = [p['id'] for p in active_passengers]
            selected_terminate = st.multiselect(
                '选择终止行程的旅客',
                passenger_options,
                key='terminate_select'
            )

            if st.button('确认终止行程', key='terminate_btn'):
                if selected_terminate:
                    on_terminate_callback(selected_terminate)
    except Exception as e:
        st.error(f"获取乘客数据失败: {e}")


# =============================================================================
# Debug Components
# =============================================================================

def render_debug_section(llm_raw_response: str = None, aip_actions: list = None):
    """Render the debug section showing LLM response and parsed actions.

    Args:
        llm_raw_response: The raw LLM response text.
        aip_actions: List of parsed actions.
    """
    st.markdown('---')
    st.markdown('### 🔧 Debug 信息')
    with st.expander('查看 LLM 原始响应和解析的 Actions', expanded=False):
        if llm_raw_response:
            st.markdown('**LLM 原始响应:**')
            st.code(llm_raw_response, language='json')
        if aip_actions:
            st.markdown('**解析后的 Actions:**')
            st.json(aip_actions)
