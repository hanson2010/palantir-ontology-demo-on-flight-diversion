# ✈️ Palantir Ontology 演示

基于 Palantir 本体论（Ontology）思想的航班备降处置演示系统，展示如何将"临时的应急处理"转变为"基于语义的系统化决策"。

## 🎯 项目目标

演示 Palantir Ontology 的核心理念：**本体论（Data）+ 大模型（Reasoning）+ 动作框架（Action Execution）的无缝闭环**。

通过航班备降场景，展示如何利用知识图谱构建语义化的数据模型，结合大语言模型进行智能推理，并自动执行决策动作。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Palantir Ontology 架构                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐           │
│   │   本体论      │     │   大模型      │     │  动作框架     │           │
│   │  (Ontology)  │ ──▶ │  (Reasoning) │ ──▶ │   (Action)   │           │
│   │              │     │              │     │              │           │
│   │  Neo4j       │     │  DeepSeek    │     │  Cypher      │           │
│   │  AuraDB      │     │  via         │     │  Updates     │           │
│   │              │     │  OpenRouter  │     │              │           │
│   └──────────────┘     └──────────────┘     └──────────────┘           │
│          ▲                                          │                   │
│          └──────────────────────────────────────────┘                   │
│                           状态同步                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## 🔄 数据流向

当您在本地运行 `streamlit run app.py` 并点击按钮时，系统执行以下流程：

### 阶段一：备降事件处置

#### 1. 本地触发
Streamlit 发送 `flight='CA123'`, `alternate='SZX'` 指令。

#### 2. 云端检索
Python 驱动向 Neo4j AuraDB 发起 Cypher 查询，检索**"富本体三元组"**：
- 🛫 航班 CA123 上的金卡旅客 Alice VIP
- 🏨 备降场 SZX 周围的协议酒店（凯越机场酒店 5 星、舒适旅馆 3 星）的剩余房间

#### 3. 智能推理
Python 将检索到的 JSON 数据和场景规则（Prompt）发送到 OpenRouter/DeepSeek：

```
推理逻辑链：
Alice VIP 是金卡 → 需要 5 星酒店 → 凯越机场酒店剩余 5 间 → 分配凯越 → 生成 BookHotel Action
```

#### 4. 状态同步（AIP Action 执行）
Python 解析 LLM 返回的 Actions JSON，向 Neo4j AuraDB 发送新的 Cypher 指令：
- 将航班状态设为 `Diverted`
- 将凯越机场酒店的房间数减 1
- 生成 `NotifyGroundService` Action，包含旅客摘要（金卡/普通旅客数量、酒店需求等）

#### 5. 实时展示
Streamlit 读取已执行的 Actions 列表，实时更新四个象限：
- 🏢 航司/运控 (OCC)：航班状态变更
- 🛂 机场地服/DCS：旅客摘要和资源需求
- 🏨 协议酒店：预订确认
- 📱 旅客：酒店分配通知

### 阶段二：补班航班准备

#### 1. 旅客终止行程
旅客可在界面中自愿选择终止行程：
- 选择终止行程的旅客将被标记为 `terminated = true`
- 该旅客不会被安排补班航班

#### 2. 创建补班航班
点击"准备补班航班"按钮后：
- 系统生成 `CreateSubFlight` Action
- 补班航班号基于原航班（如 CA123 → CA123A）
- 仅包含未终止行程的旅客
- 通知地服部门补班航班详情

## 📦 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 前端 | Streamlit | 交互式 Web 界面 |
| 知识图谱 | Neo4j AuraDB | 本体数据存储与查询 |
| LLM 推理 | DeepSeek (via OpenRouter) | 语义推理与决策生成 |
| 框架 | LangChain | LLM 集成与 Prompt 管理 |

## 🚀 快速开始

### 前置条件

- Python 3.10+
- Neo4j AuraDB 实例（免费版即可）
- OpenRouter API Key

### 安装步骤

1. **克隆仓库**
   ```bash
   git clone https://github.com/your-username/palantir-ontology-demo-on-flight-diversion.git
   cd palantir-ontology-demo-on-flight-diversion
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   ```bash
   cp .env.example .env
   ```

   编辑 `.env` 文件，填入您的凭据：
   ```
   NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password
   OPENAI_BASE_URL=https://openrouter.ai/api/v1
   OPENAI_API_KEY=your_api_key
   MODEL_ID=deepseek/deepseek-chat
   ```

4. **初始化 Neo4j 数据**

   在 Neo4j AuraDB 控制台中运行 [`data/create_objects.cypher`](data/create_objects.cypher) 脚本创建示例数据。

5. **启动应用**
   ```bash
   streamlit run app.py
   ```

## 📁 项目结构

```
palantir-ontology-demo-on-flight-diversion/
├── data/
│   └── create_objects.cypher    # Neo4j 示例数据初始化脚本
├── app.py              # 主应用程序（Streamlit + Neo4j + LLM 集成）
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量模板
├── .env                # 环境变量（需自行创建）
├── LICENSE             # MIT 许可证
└── README.md           # 项目文档
```

## 🎓 Palantir Ontology 核心概念

### 本体论（Ontology）

本体论是 Palantir Ontology 的数据基础，它将现实世界的实体及其关系建模为语义化的知识图谱：

- **实体（Objects）**：航班、旅客、机场、酒店等
- **属性（Properties）**：航班状态、旅客会员等级、酒店星级等
- **关系（Links）**：旅客登机、机场协议酒店等

#### 示例本体结构

```
(Flight:CA123 {status: 'EN_ROUTE'})
    ├── [:DESTINED_FOR] → (Airport:CAN)
    └── [:HAS_SUB_FLIGHT] → (SubFlight:CA123A)

(Passenger:Alice VIP {loyalty: 'GOLD'})
    └── [:ON_BOARD] → (Flight:CA123)

(Airport:SZX)
    └── [:HAS_PROTOCOL_HOTEL] → (Hotel:Hyatt Airport {star: 5, availableRooms: 5})
    └── [:HAS_PROTOCOL_HOTEL] → (Hotel:Comfort Inn {star: 3, availableRooms: 60})
```

### 推理引擎（Reasoning）

利用大语言模型的语义理解能力，基于本体数据和业务规则进行智能推理：

- 理解旅客会员等级与酒店星级的对应关系
- 考虑机组工时限制对航班调度的影响
- 生成符合业务逻辑的决策建议

### 动作框架（Action Execution）

将推理结果转化为可执行的系统操作：

| Action 类型 | 说明 | 参数 |
|------------|------|------|
| `SetFlightStatus` | 更新航班状态 | `iata`, `status` |
| `BookHotel` | 预订酒店 | `passengerId`, `hotelName` |
| `UpdateHotelInventory` | 更新酒店库存 | `name` |
| `NotifyGroundService` | 通知地服（含旅客摘要） | `summary`, `message` |
| `CreateSubFlight` | 创建补班航班 | `mainFlight`, `subFlightIata`, `scheduledTime` |
| `TerminatePassengerJourney` | 终止旅客行程 | `passengerId` |

## 🔧 关键代码解析

### 本体数据检索

```python
def get_ontology_data(flight_iata, alternate_iata):
    query = '''
    MATCH (f:Flight {iata: $flight})
    OPTIONAL MATCH (p:Passenger)-[:ON_BOARD]->(f)
    MATCH (a:Airport {iata: $alternate})-[:HAS_PROTOCOL_HOTEL]->(h:Hotel)
    OPTIONAL MATCH (f)-[:HAS_SUB_FLIGHT]->(sf:SubFlight)
    RETURN
        {iata: f.iata, status: f.status} as flight,
        collect(DISTINCT {id: p.id, name: p.name, loyalty: p.loyalty, terminated: COALESCE(p.terminated, false)}) as passengers,
        {iata: a.iata, name: a.name} as alternateAirport,
        collect(DISTINCT {name: h.name, star: h.star, availableRooms: h.availableRooms}) as hotels,
        sf as subFlight
    '''
    # ...
```

### Ontology 推理核心

```python
diversion_prompt_template = '''
You are the reasoning core of Palantir Ontology. A flight diversion event has occurred.
You need to analyze the current state of the Ontology (provided below) and generate a JSON list of Actions to execute in the system.

Ontology Data:
{ontology_data}

Passenger Summary for Ground Service:
{passenger_summary}

Rules:
1. Gold Passengers get 5-star hotels if available.
2. Regular Passengers get 3-star hotels.
3. Generate NotifyGroundService action with detailed passenger summary.
4. Exclude terminated passengers from hotel bookings.

Expected Action JSON Schema (List of Actions):
[
    { "type": "SetFlightStatus", "params": { "iata": "string", "status": "string" } },
    { "type": "NotifyGroundService", "params": { "summary": {...}, "message": "string" } },
    { "type": "BookHotel", "params": { "passengerId": "string", "hotelName": "string" } },
    { "type": "UpdateHotelInventory", "params": { "name": "string" } }
]

Generate ONLY the JSON array, no other text.
'''
```

### 动作执行

```python
def execute_action(action_json):
    actions = extract_json_from_response(action_json)
    with neo4j_driver.session() as session:
        for action in actions:
            if action['type'] == 'SetFlightStatus':
                session.run('MATCH (f:Flight {iata: $iata}) SET f.status = $status', **action['params'])
            elif action['type'] == 'UpdateHotelInventory':
                session.run('MATCH (h:Hotel {name: $name}) SET h.availableRooms = h.availableRooms - 1', **action['params'])
            # ...
    return actions
```

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [Palantir Technologies](https://www.palantir.com/) - AIP 平台灵感来源
- [Neo4j](https://neo4j.com/) - 图数据库技术
- [DeepSeek](https://www.deepseek.com/) - 大语言模型
- [OpenRouter](https://openrouter.ai/) - LLM API 网关
