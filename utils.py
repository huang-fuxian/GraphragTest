
from knowledge_graph_utils import build_dynamic_cypher_query, get_relevant_nodes_and_relations, load_graph_from_json, get_graph_overview, get_neo4j_driver, search_nodes_by_name
from api_utils import LocalEmbeddings, test_api_connection, test_embeddings, get_api_client, get_context_aware_response, query_knowledge_graph, clean_api_response,get_context_aware_response_stream
import re
from openai import OpenAI
from config import LLM_CONFIG,  EMBEDDING_CONFIG, NEO4J_CONFIG,GRAPH_CONFIG
# from langchain_neo4j import Neo4jGraph
from py2neo import Graph, Node, Relationship
API_KEY = LLM_CONFIG["API_KEY"]
LLM_API_URL = LLM_CONFIG["API_URL"]
Model_name = LLM_CONFIG["Model"]
def graph_rag_fun(cypher_query, graph):
    search_result = None
    full_stream_text = None
    
    try:
        search_result = graph.run(cypher_query).data()
        if search_result and len(search_result) > 0:
            print(f"🔍 查看查询结果 ({len(search_result)} 条)")
            import json
            max_display = 10
            max_chars = 4000
            display_list = []
            total_chars = 0
            for item in search_result[:max_display]:
                item_str = json.dumps(item, ensure_ascii=False)
                if total_chars + len(item_str) > max_chars:
                    break
                display_list.append(item)
                total_chars += len(item_str)
            if not display_list and search_result:
                # 如果第一条就超长，至少展示一条
                display_list = [search_result[0]]
            summary_prompt = f"用户问题：{''}\n查询结果：{search_result[:8]}\n请用中文总结这些结果。"
            print(summary_prompt)
            try:
                print("**🤖 AI智能总结：**")
                client = OpenAI(api_key=API_KEY, base_url=LLM_API_URL)
                full_stream_text = ""
                for chunk in get_context_aware_response_stream(
                    question=summary_prompt,
                    history=[],
                    client=client,
                    model_name=Model_name,
                    max_tokens=2000
                ):
                    full_stream_text += chunk 
                if full_stream_text and len(full_stream_text.strip()) > 5:
                    print(f"✅ AI总结生成成功:{full_stream_text}")
                    
                else:
                    print("AI总结内容为空")
            except Exception as e:
                print(f"AI总结失败: {str(e)}") 
    except Exception as e:
        print(f"❌ Cypher 执行出错: {str(e)}")
    return search_result, full_stream_text
    
def configure_neo4j():
    """配置Neo4j连接"""
    neo4j_uri = NEO4J_CONFIG["uri"]
    neo4j_username =  NEO4J_CONFIG["user"]
    neo4j_password =  NEO4J_CONFIG["password"]
    graph = Graph(neo4j_uri, auth=(neo4j_username, neo4j_password))
    
    return graph

def extract_cypher_from_llm_output(llm_output):
    # 1. 先找 Cypher: 代码块
    match = re.search(r'Cypher:\s*([\s\S]+?)(?:解释|$)', llm_output)
    if match:
        cypher = match.group(1).strip()
    else:
        # 2. 再找"以下的Cypher查询语句"后面的代码块
        match = re.search(r'Cypher查询语句[：:]?\s*([\s\S]+?)(?:\n\n|$)', llm_output)
        if match:
            cypher = match.group(1).strip()
        else:
            # 3. 再找 MATCH 开头的代码块
            match = re.search(r'(MATCH[^\n]+(?:\n[^\n]+)*)', llm_output)
            if match:
                cypher = match.group(1).strip()
            else:
                return None
    # 去除代码块标记和前缀
    cypher = cypher.strip('`')
    cypher = re.sub(r'^cypher\s+', '', cypher, flags=re.IGNORECASE)
    cypher = re.sub(r'^```cypher\s*', '', cypher, flags=re.IGNORECASE)
    cypher = re.sub(r'```$', '', cypher)
    return cypher.strip()

def get_api_client(api_type: str=None, api_key: str=None, url: str=None) -> OpenAI:
    """获取API客户端""" 
    if api_key==None:
        api_key=LLM_CONFIG["API_KEY"]
    if url==None:
        url=LLM_CONFIG["API_URL"]
    client = OpenAI(api_key=api_key, base_url=url)
    return client

def ensure_cypher_limit(cypher_query, limit=20):
    # 如果已有 LIMIT，替换为20；否则追加 LIMIT 20
    if re.search(r'LIMIT \d+', cypher_query, re.IGNORECASE):
        cypher_query = re.sub(r'LIMIT \d+', f'LIMIT {limit}', cypher_query, flags=re.IGNORECASE)
    else:
        cypher_query += f' LIMIT {limit}'
    return cypher_query

def context_aware_kg_qa(prompt, graph, qa_system=None, history=[]):
    """
    同步方式：结合Neo4j知识图谱和历史上下文，生成大模型回答
    """
    # 1. 获取对话上下文
    # conversation_context = qa_system.get_context_summary()
    # graph_context = qa_system.get_graph_context()

    # 2. 基于关键词查询图谱
    relevant_info = get_relevant_nodes_and_relations(
         prompt, GRAPH_CONFIG['allowed_nodes'], GRAPH_CONFIG['allowed_relationships']
    )
    cypher_query = build_dynamic_cypher_query(relevant_info, prompt)
    cypher_query = ensure_cypher_limit(cypher_query, limit=20)
    try:
        query_result = graph.run(cypher_query).data()
    except Exception as e:
        query_result = [f"Cypher查询失败: {str(e)}"]

    # 3. 构造大模型输入
    system_prompt = f"""
                    你是木结构建筑知识图谱查询助手。根据用户问题生成Cypher查询。

                    {cypher_schema}

                    请根据用户的自然语言问题，生成最合适的 Cypher 查询，并用中文简要解释你的思路。

                    重要提示：
                    1. 这是一个专业的木结构建筑知识图谱，包含项目、材料、结构类型、连接方式等丰富信息
                    2. 所有节点都有"名称"属性（除了定义、材料特点、树种特性、木材特点、应用场景使用"描述"属性）
                    3. 项目是主要实体，其他节点通过关系连接到项目
                    4. 关系方向：项目 -> 其他节点
                    5. 层次关系使用[:包含]关系，如结构类型、木材类型、树种等都有层次结构
                    6. 木材类型有多个别名，可以通过别名查询（如CLT、正交胶合木等）
                    7. 数值比较需要使用toInteger()函数转换字符串为数字
                    8. 如果不确定具体名称，可以使用模糊查询：WHERE n.名称 CONTAINS '关键词'
                    9. 如果用户问题中提到"建筑"，则默认指的是"项目"节点。
                    10. 如果返回的内容中包含"照片"（图片URL或图片标签）和"链接"，请将它们分别单独放在一行，照片在上，链接在下，避免同一行展示。

                    相关节点：{relevant_info.get('nodes', [])}
                    相关关系：{relevant_info.get('relations', [])}

                    请生成简洁的Cypher查询并用中文解释。
                    """
    # 4. 构造历史消息
    messages = [{"role": "system", "content": system_prompt}]
    messages += history
    messages.append({"role": "user", "content": prompt})

    # 5. 调用大模型
    client = get_api_client()
    response = client.chat.completions.create(
        model=LLM_CONFIG["Model"],
        messages=messages,
        max_tokens=400,  # 适中的长度
        temperature=0.3  # 降低随机性，提高速度
    )
    return response.choices[0].message.content.strip()



# 在文件顶部或 context_aware_kg_qa 前定义 schema 变量：
cypher_schema = '''
你正在访问的木结构建筑知识图谱，包含以下完整结构：

// 核心节点类型：
// 项目 (项目) - 主要实体，包含属性：名称, 建筑面积, 图片, 链接, 大跨, 跨度, 高层, 层数, 高度, 状态
// 功能 (功能) - 项目功能分类
// 国家 (国家) - 项目所在国家
// 城市 (城市) - 项目所在城市
// 面积分级 (面积分级) - 项目面积等级
// 建成年份 (建成年份) - 项目建成年份
// 建筑师团队 (建筑师团队) - 设计团队
// 结构类型 (结构类型) - 建筑结构类型，包含层次关系
// 结构工程 (结构工程) - 结构工程相关
// 施工 (施工) - 施工单位
// 厂家 (厂家) - 材料厂家
// 建筑特色 (建筑特色) - 建筑特色
// 其他材料 (其他材料) - 其他建筑材料
// 构件 (构件) - 建筑构件
// 材料特点 (材料特点) - 材料特点描述
// 连接方式 (连接方式) - 连接方式，包含层次关系
// 定义 (定义) - 各种定义描述
// 树种 (树种) - 木材树种，包含层次关系
// 树种特性 (树种特性) - 树种特性描述
// 木材类型 (木材类型) - 木材类型，包含层次关系
// 木材特点 (木材特点) - 木材特点描述
// 应用场景 (应用场景) - 应用场景描述
// 别名 (别名) - 各种别名

// 主要关系类型：
// (项目)-[:功能]->(功能)
// (项目)-[:国家]->(国家)
// (项目)-[:城市]->(城市)
// (项目)-[:面积分级]->(面积分级)
// (项目)-[:建成年份]->(建成年份)
// (项目)-[:建筑师团队]->(建筑师团队)
// (项目)-[:结构类型]->(结构类型)
// (项目)-[:结构工程]->(结构工程)
// (项目)-[:施工]->(施工)
// (项目)-[:厂家]->(厂家)
// (项目)-[:建筑特色]->(建筑特色)
// (项目)-[:其他材料]->(其他材料)
// (项目)-[:树种]->(树种)
// (项目)-[:木材类型]->(木材类型)
// (项目)-[:连接方式]->(连接方式)

// 层次关系：
// (结构类型)-[:包含]->(结构类型)  // 如：大跨木结构->实腹梁结构
// (连接方式)-[:包含]->(连接方式)  // 连接方式的层次关系
// (树种)-[:包含]->(树种)          // 树种的层次关系
// (木材类型)-[:包含]->(木材类型)  // 木材类型的层次关系

// 其他关系：
// (其他材料)-[:used_in]->(构件)
// (其他材料)-[:材料特点]->(材料特点)
// (树种)-[:used_in]->(构件)
// (树种)-[:树种特性]->(树种特性)
// (树种)-[:国家]->(国家)
// (木材类型)-[:used_in]->(构件)
// (木材类型)-[:made_of]->(树种)
// (木材类型)-[:木材特点]->(木材特点)
// (木材类型)-[:应用场景]->(应用场景)
// (木材类型)-[:具有别名]->(别名)
// (结构类型)-[:定义]->(定义)
// (连接方式)-[:定义]->(定义)

// 常用查询模式：
// 1. 查询特定功能的项目：MATCH (p:项目)-[:功能]->(f:功能 {名称: '办公'}) RETURN p
// 2. 查询特定国家的项目：MATCH (p:项目)-[:国家]->(c:国家 {名称: '中国'}) RETURN p
// 3. 查询特定结构类型：MATCH (p:项目)-[:结构类型]->(s:结构类型 {名称: '钢结构'}) RETURN p
// 4. 查询特定年份的项目：MATCH (p:项目)-[:建成年份]->(y:建成年份 {名称: '2020'}) RETURN p
// 5. 查询特定建筑师团队：MATCH (p:项目)-[:建筑师团队]->(a:建筑师团队 {名称: '团队名称'}) RETURN p
// 6. 查询项目及其所有关联信息：MATCH (p:项目)-[r]-(n) RETURN p, r, n
// 7. 查询特定城市的项目：MATCH (p:项目)-[:城市]->(c:城市 {名称: '北京'}) RETURN p
// 8. 查询特定面积分级：MATCH (p:项目)-[:面积分级]->(a:面积分级 {名称: '大型'}) RETURN p
// 9. 查询有某属性的项目：MATCH (p:项目) WHERE p.高层 IS NOT NULL RETURN p
// 10. 查询层数大于10的项目：MATCH (p:项目) WHERE toInteger(p.层数) > 10 RETURN p
// 11. 查询建筑面积大于10000的项目：MATCH (p:项目) WHERE toInteger(p.建筑面积) > 10000 RETURN p
// 12. 查询使用特定树种的项目：MATCH (p:项目)-[:树种]->(t:树种 {名称: '松木'}) RETURN p
// 13. 查询使用特定木材类型的项目：MATCH (p:项目)-[:木材类型]->(m:木材类型 {名称: 'CLT'}) RETURN p
// 14. 查询特定连接方式的项目：MATCH (p:项目)-[:连接方式]->(c:连接方式 {名称: '榫卯连接'}) RETURN p
// 15. 查询结构类型的层次关系：MATCH (s1:结构类型)-[:包含]->(s2:结构类型) RETURN s1, s2
// 16. 查询木材类型的别名：MATCH (m:木材类型)-[:具有别名]->(a:别名) RETURN m, a
// 17. 查询特定构件的使用情况：MATCH (m)-[:used_in]->(c:构件 {名称: '梁'}) RETURN m, c
// 18. 查询特定应用场景的木材类型：MATCH (m:木材类型)-[:应用场景]->(a:应用场景 {描述: '结构构件'}) RETURN m, a

// 复杂查询示例：
// 19. 查询使用CLT且层数大于5的项目：
//     MATCH (p:项目)-[:木材类型]->(m:木材类型 {名称: '正交胶合木(CLT)'})
//     WHERE toInteger(p.层数) > 5
//     RETURN p
// 20. 查询大跨木结构下的所有具体结构类型：
//     MATCH (s1:结构类型 {名称: '大跨木结构'})-[:包含]->(s2:结构类型)
//     RETURN s2
// 21. 查询特定树种的所有特性：
//     MATCH (t:树种 {名称: '松木'})-[:树种特性]->(f:树种特性)
//     RETURN t, f
// 22. 查询使用特定连接方式的高层项目：
//     MATCH (p:项目)-[:连接方式]->(c:连接方式 {名称: '榫卯连接'})
//     WHERE p.高层 IS NOT NULL
//     RETURN p, c

// Few-shot训练样例：
// 用户问题：查找有高层属性的所有项目
// Cypher：MATCH (p:项目) WHERE p.高层 IS NOT NULL RETURN p
// 用户问题：查询所有层数大于10的项目
// Cypher：MATCH (p:项目) WHERE toInteger(p.层数) > 10 RETURN p
// 用户问题：查找使用CLT的项目
// Cypher：MATCH (p:项目)-[:木材类型]->(m:木材类型 {名称: '正交胶合木(CLT)'}) RETURN p
// 用户问题：查询大跨木结构的所有子类型
// Cypher：MATCH (s1:结构类型 {名称: '大跨木结构'})-[:包含]->(s2:结构类型) RETURN s2
// 用户问题：查找壳结构的大跨项目
// Cypher：MATCH (p:项目)-[:结构类型]->(m:结构类型 {名称: '壳结构'}) WHERE p.大跨 IS NOT NULL RETURN p

// 注意事项：
// - 所有节点都有"名称"属性（除了定义、材料特点、树种特性、木材特点、应用场景使用"描述"属性）
// - 项目节点有额外的属性如建筑面积、图片、链接、大跨、跨度、高层、层数、高度、状态
// - 关系都是单向的，从项目指向其他节点
// - 层次关系使用[:包含]关系
// - 查询时注意使用正确的节点标签和属性名
// - 数值比较需要使用toInteger()函数转换字符串为数字
// - 木材类型有多个别名，可以通过别名查询
'''
