import os
import json
import time

from dotenv import load_dotenv
import streamlit as st
from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate


# --- 1. 初始化云端连接 ---
load_dotenv()
neo4j_driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)

llm = ChatOpenAI(
    base_url=os.getenv('OPENAI_BASE_URL'),
    api_key=os.getenv('OPENAI_API_KEY'),
    model=os.getenv('MODEL_ID'),
    temperature=0
)


def invoke_llm_with_retry(prompt, max_retries=3, delay=2):
    """带重试机制的 LLM 调用"""
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
                    delay *= 2  # 指数退避
            else:
                raise e
    raise last_error

# --- 2. 逻辑函数 ---

def get_ontology_data(flight_iata, alternate_iata):
    """从Neo4j AuraDB检索相关的本体数据"""
    query = '''
    MATCH (f:Flight {iata: $flight})
    OPTIONAL MATCH (p:Passenger)-[:ON_BOARD]->(f)
    MATCH (a:Airport {iata: $alternate})-[:HAS_PROTOCOL_HOTEL]->(h:Hotel)
    OPTIONAL MATCH (f)-[:HAS_SUB_FLIGHT]->(sf:SubFlight)
    RETURN
        {iata: f.iata, status: f.status} as flight,
        collect(DISTINCT CASE WHEN p IS NOT NULL THEN {id: p.id, name: p.name, loyalty: p.loyalty, terminated: COALESCE(p.terminated, false)} ELSE NULL END) as passengers,
        {iata: a.iata, name: a.name} as alternateAirport,
        collect(DISTINCT {name: h.name, star: h.star, availableRooms: h.availableRooms}) as hotels,
        sf as subFlight
    '''
    with neo4j_driver.session() as session:
        result = session.run(query, flight=flight_iata, alternate=alternate_iata)
        record = result.single()
        if record is None:
            raise ValueError(f"未找到航班 {flight_iata} 或备降机场 {alternate_iata} 的数据")
        # 过滤掉 null 乘客
        passengers = [p for p in record['passengers'] if p is not None]
        return {
            'flight': record['flight'],
            'passengers': passengers,
            'alternateAirport': record['alternateAirport'],
            'hotels': record['hotels'],
            'subFlight': record['subFlight']
        }

def get_passenger_summary(passengers):
    """生成乘客摘要供地服人员参考"""
    gold_passengers = [p for p in passengers if p.get('loyalty', '').upper() == 'GOLD' and not p.get('terminated')]
    regular_passengers = [p for p in passengers if p.get('loyalty', '').upper() == 'REGULAR' and not p.get('terminated')]
    terminated_passengers = [p for p in passengers if p.get('terminated')]

    summary = {
        'total': len(passengers),
        'gold_count': len(gold_passengers),
        'regular_count': len(regular_passengers),
        'terminated_count': len(terminated_passengers),
        'gold_names': [p['id'] for p in gold_passengers],
        'regular_names': [p['id'] for p in regular_passengers],
        'terminated_names': [p['id'] for p in terminated_passengers],
        'hotel_needs': {
            '5_star': len(gold_passengers),
            '3_star': len(regular_passengers)
        }
    }
    return summary

def extract_json_from_response(response_text):
    """从LLM响应中提取JSON数组"""
    import re
    # 尝试直接解析
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 markdown 代码块中的 JSON
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试提取方括号包围的 JSON 数组
    array_match = re.search(r'\[[\s\S]*\]', response_text)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 响应中提取有效的 JSON:\n{response_text[:500]}...")

def execute_action(action_json):
    """根据LLM生成的JSON指令，同步更新Neo4j状态 (AIP Action 执行)"""
    actions = extract_json_from_response(action_json)
    with neo4j_driver.session() as session:
        for action in actions:
            if action['type'] == 'SetFlightStatus':
                session.run('MATCH (f:Flight {iata: $iata}) SET f.status = $status', **action['params'])
            elif action['type'] == 'UpdateHotelInventory':
                session.run('MATCH (h:Hotel {name: $name}) SET h.availableRooms = h.availableRooms - 1', **action['params'])
            elif action['type'] == 'CreateSubFlight':
                params = action['params']
                session.run('''
                    MATCH (f:Flight {iata: $mainFlight})
                    CREATE (sf:SubFlight {
                        iata: $subFlightIata,
                        scheduledTime: $scheduledTime,
                        status: 'Planned'
                    })
                    CREATE (f)-[:HAS_SUB_FLIGHT]->(sf)
                    WITH sf
                    MATCH (f:Flight {iata: $mainFlight})-[:ON_BOARD]->(p:Passenger)
                    WHERE NOT p.terminated = true
                    CREATE (sf)-[:CARRIES]->(p)
                ''', **params)
            elif action['type'] == 'TerminatePassengerJourney':
                session.run('''
                    MATCH (p:Passenger {id: $passengerId})
                    SET p.terminated = true
                ''', **action['params'])
    return actions

# --- 3. 提示词工程 (AIP reasoning logic) ---

diversion_prompt_template = '''
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

subflight_prompt_template = '''
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

# --- 4. Streamlit 页面布局 ---
st.set_page_config(layout='wide', page_title='Palantir AIP 本体论演示')

# 初始化 session state
if 'aip_actions' not in st.session_state:
    st.session_state['aip_actions'] = []
if 'diversion_triggered' not in st.session_state:
    st.session_state['diversion_triggered'] = False
if 'terminated_passengers' not in st.session_state:
    st.session_state['terminated_passengers'] = []

# 顶部标题和 AIP 信息（居中）
st.markdown("""
<div style="text-align: center;">
    <h1>✈️ Palantir AIP 本体论演示</h1>
    <p>本体论（Data）+ 大模型（Reasoning）+ 动作框架（Action Execution）的无缝闭环</p>
</div>
<hr>
""", unsafe_allow_html=True)

# 四列布局
col1, col2, col3, col4 = st.columns(4)

actions = st.session_state.get('aip_actions', [])

# 第一列：航司/运控 (OCC) - 包含控制面板
with col1:
    st.header('🏢 航司/运控 (OCC)')

    # OCC 控制面板
    st.subheader('控制面板')
    flight_to_divert = st.selectbox('选择航班', ['CA123'], key='flight_select')
    alternate_airport = st.selectbox('选择备降场', ['SZX'], key='airport_select')

    # 备降事件按钮
    if st.button('🚨 发起备降事件', key='trigger'):
        with st.spinner('Calling AIP Reasoning Core...'):
            # 步骤 1: 调用 Neo4j AuraDB
            ontology_data = get_ontology_data(flight_to_divert, alternate_airport)
            passenger_summary = get_passenger_summary(ontology_data['passengers'])

            # 步骤 2: 调用 OPENAI 云端推理
            final_prompt = diversion_prompt_template.format(
                ontology_data=json.dumps(ontology_data, ensure_ascii=False),
                passenger_summary=json.dumps(passenger_summary, ensure_ascii=False)
            )
            response = invoke_llm_with_retry(final_prompt)

            # DEBUG: 显示 LLM 原始响应
            st.session_state['llm_raw_response'] = response.content

            # 步骤 3: 同步 Neo4j 状态
            executed_actions = execute_action(response.content)
            st.session_state['aip_actions'] = executed_actions
            st.session_state['diversion_triggered'] = True
            st.success('✅ AIP 推理完成')
            st.rerun()

    # 准备补班航班按钮
    if st.session_state.get('diversion_triggered'):
        st.markdown('---')
        if st.button('🛫 准备补班航班', key='subflight'):
            with st.spinner('Creating sub-flight...'):
                ontology_data = get_ontology_data(flight_to_divert, alternate_airport)

                final_prompt = subflight_prompt_template.format(
                    ontology_data=json.dumps(ontology_data, ensure_ascii=False)
                )
                response = invoke_llm_with_retry(final_prompt)

                executed_actions = execute_action(response.content)
                st.session_state['aip_actions'] = st.session_state['aip_actions'] + executed_actions
                st.success('✅ 补班航班已创建！')
                st.rerun()

    # 显示航班状态
    st.markdown('---')
    st.subheader('航班状态')
    for act in actions:
        if act['type'] == 'SetFlightStatus' and act['params'].get('iata') == flight_to_divert:
            st.info(f"✈️ 航班 {act['params']['iata']} 状态: **{act['params']['status']}**")
        elif act['type'] == 'CreateSubFlight':
            params = act['params']
            st.success(f"🛫 补班航班 **{params['subFlightIata']}**\n\n计划时间: {params['scheduledTime']}")

# 第二列：机场地服/DCS
with col2:
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

# 第三列：协议酒店
with col3:
    st.header('🏨 协议酒店')
    booked_hotels = [act['params']['hotelName'] for act in actions if act['type'] == 'BookHotel']
    if booked_hotels:
        st.success(f"AIP 自动预订确认：\n\n{', '.join(set(booked_hotels))}")

# 第四列：旅客
with col4:
    st.header('📱 旅客')

    # 旅客自愿终止行程选项
    st.markdown("### 🚫 自愿终止行程")
    st.markdown("*旅客可选择终止行程，将不会被安排补班航班*")

    # 获取当前乘客列表
    if st.session_state.get('diversion_triggered'):
        try:
            ontology_data = get_ontology_data(flight_to_divert, alternate_airport)
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
                        terminate_actions = []
                        for passenger_id in selected_terminate:
                            terminate_actions.append({
                                'type': 'TerminatePassengerJourney',
                                'params': {'passengerId': passenger_id}
                            })
                        # 执行终止行程
                        with neo4j_driver.session() as session:
                            for action in terminate_actions:
                                session.run('''
                                    MATCH (p:Passenger {id: $passengerId})
                                    SET p.terminated = true
                                ''', **action['params'])
                        st.session_state['terminated_passengers'] = st.session_state.get('terminated_passengers', []) + selected_terminate
                        st.success(f"已终止 {len(selected_terminate)} 位旅客的行程")
                        st.rerun()
        except Exception as e:
            st.error(f"获取乘客数据失败: {e}")

    # 显示酒店预订信息
    st.markdown("### 🏨 酒店预订")
    passenger_msgs = [f"{act['params']['passengerId']}: 已预定 {act['params']['hotelName']}" for act in actions if act['type'] == 'BookHotel']
    for msg in passenger_msgs:
        st.chat_message('ai').write(msg)

    # 显示已终止行程的旅客
    terminated = st.session_state.get('terminated_passengers', [])
    if terminated:
        st.markdown("### ⛔ 已终止行程")
        for p in terminated:
            st.markdown(f"- {p} (已终止)")

# --- DEBUG 区域 ---
st.markdown('---')
st.markdown('### 🔧 Debug 信息')
with st.expander('查看 LLM 原始响应和解析的 Actions', expanded=False):
    if st.session_state.get('llm_raw_response'):
        st.markdown('**LLM 原始响应:**')
        st.code(st.session_state['llm_raw_response'], language='json')
    if st.session_state.get('aip_actions'):
        st.markdown('**解析后的 Actions:**')
        st.json(st.session_state['aip_actions'])
