
from knowledge_graph_utils import build_dynamic_cypher_query, get_relevant_nodes_and_relations, load_graph_from_json, get_graph_overview, get_neo4j_driver, search_nodes_by_name
from api_utils import LocalEmbeddings, test_api_connection, test_embeddings, get_api_client, get_context_aware_response, query_knowledge_graph, clean_api_response,get_context_aware_response_stream
import re
import streamlit as st  
import jieba
from openai import OpenAI
from config import LLM_CONFIG,  EMBEDDING_CONFIG, NEO4J_CONFIG,GRAPH_CONFIG
# from langchain_neo4j import Neo4jGraph
from py2neo import Graph, Node, Relationship
API_KEY = LLM_CONFIG["API_KEY"]
LLM_API_URL = LLM_CONFIG["API_URL"]
Model_name = LLM_CONFIG["Model"]
def graph_rag_fun(cypher_query, graph, question):
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
            summary_prompt = f"用户问题：{question}\n查询结果：{search_result[:8]}\n请用中文总结这些结果。"
            print(summary_prompt)
            try:
                print("**🤖 AI智能总结：**")
                client = OpenAI(api_key=API_KEY, base_url=LLM_API_URL)
                placeholder = st.empty()
                full_stream_text = ""
                for chunk in get_context_aware_response_stream(
                    question=summary_prompt,
                    history=[],
                    client=client,
                    model_name=Model_name,
                    max_tokens=2000
                ):
                    full_stream_text += chunk 
                    placeholder.markdown(full_stream_text) 
                if full_stream_text and len(full_stream_text.strip()) > 5:
                    print(f"✅ AI总结生成成功:{full_stream_text}")
                    
                else:
                    print("AI总结内容为空")
            except Exception as e:
                print(f"AI总结失败: {str(e)}") 
    except Exception as e:
        print(f"❌ Cypher 执行出错: {str(e)}")
    return search_result, full_stream_text
    
def configure_neo4j(db_name):
    """配置Neo4j连接"""
    neo4j_uri = NEO4J_CONFIG[db_name]["uri"]
    neo4j_username =  NEO4J_CONFIG[db_name]["user"]
    neo4j_password =  NEO4J_CONFIG[db_name]["password"]
    graph = Graph(neo4j_uri, auth=(neo4j_username, neo4j_password))
    
    return graph

def simple_extract_cypher(input_str):
    if input_str.strip().startswith("```"):
        cypher_block = input_str.split("```")[1]
    else:
        cypher_block = input_str
    # 移除首尾空白及开头的"cypher"标记
    if cypher_block.startswith("cypher"):
        cypher_block = cypher_block[6:]  # 移除"cypher\n"
 
    return cypher_block.strip().replace("\n", " ")

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

def construct_db_cypher():
    """
    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH 
    trim(row.项目名称) AS projectName,
    trim(row.建筑面积) AS area,
    trim(row.图片) AS image,
    trim(row.链接) AS link,
    trim(row.大跨) AS longSpan,
    trim(row.跨度) AS span,
    trim(row.高层) AS highRise,
    trim(row.层数) AS floors,
    trim(row.高度) AS height,
    trim(row.状态) AS status
    WHERE projectName IS NOT NULL AND projectName <> "" AND projectName <> "\\"

    MERGE (p:项目 {名称: projectName})
    SET 
    p.建筑面积 = area,
    p.图片 = image,
    p.链接 = link,
    p.大跨 = longSpan,
    p.跨度 = span,
    p.高层 = highRise,
    p.层数 = floors,
    p.高度 = height,
    p.状态 = status


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH 
    trim(row.项目名称) AS projectName,
    trim(row.功能) AS function,
    trim(row.国家) AS country,
    trim(row.城市) AS city,
    trim(row.面积分级) AS areaLevel,
    trim(row.建成年份) AS year
    WHERE projectName IS NOT NULL AND projectName <> "" AND projectName <> "\\"

    MATCH (p:项目 {名称: projectName})

    FOREACH (_ IN CASE WHEN function IS NOT NULL AND function <> "" THEN [1] ELSE [] END |
    MERGE (f:功能 {名称: function})
    MERGE (p)-[:具有建筑功能]->(f)
    )

    FOREACH (_ IN CASE WHEN country IS NOT NULL AND country <> "" THEN [1] ELSE [] END |
    MERGE (c:国家 {名称: country})
    MERGE (p)-[:位于国家]->(c)
    )

    FOREACH (_ IN CASE WHEN city IS NOT NULL AND city <> "" THEN [1] ELSE [] END |
    MERGE (ci:城市 {名称: city})
    MERGE (p)-[:位于城市]->(ci)
    )

    FOREACH (_ IN CASE WHEN areaLevel IS NOT NULL AND areaLevel <> "" THEN [1] ELSE [] END |
    MERGE (a:面积分级 {名称: areaLevel})
    MERGE (p)-[:属于面积分级]->(a)
    )

    FOREACH (_ IN CASE WHEN year IS NOT NULL AND year <> "" THEN [1] ELSE [] END |
    MERGE (y:建成年份 {名称: year})
    MERGE (p)-[:建成时间]->(y)
    )


    UNWIND [
    {名称: "超小型", 分类标准: "< 100㎡"},
    {名称: "小型", 分类标准: "100㎡ – 500㎡"},
    {名称: "中型", 分类标准: "500㎡ – 2000㎡"},
    {名称: "大型", 分类标准: "2000㎡ – 10000㎡"},
    {名称: "超大型", 分类标准: "≥ 10000㎡"}
    ] AS item
    MATCH (a:面积分级 {名称: item.名称})
    SET a.分类标准 = item.分类标准



    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName,
        [row.建筑师团队1, row.建筑师团队2, row.建筑师团队3, row.建筑师团队4] AS teams
    WHERE projectName IS NOT NULL AND projectName <> ""

    MATCH (p:项目 {名称: projectName})
    UNWIND teams AS team
    WITH p, trim(team) AS name
    WHERE name IS NOT NULL AND name <> "" AND name <> "\\"
    MERGE (a:建筑师团队 {名称: name})
    MERGE (p)-[:由建筑师团队设计]->(a)


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName,
        [row.结构类型1, row.结构类型2] AS structureList
    WHERE projectName IS NOT NULL AND projectName <> ""

    MATCH (p:项目 {名称: projectName})
    UNWIND structureList AS st
    WITH p, trim(st) AS stname
    WHERE stname IS NOT NULL AND stname <> "" AND stname <> "\\"
    MERGE (s:结构类型 {名称: stname})
    MERGE (p)-[:采用结构类型]->(s)


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName,
        split(coalesce(row.结构工程, ""), "，") + split(coalesce(row.结构工程, ""), ",") AS engineers
    WHERE projectName IS NOT NULL AND projectName <> ""

    MATCH (p:项目 {名称: projectName})
    UNWIND engineers AS e
    WITH p, trim(e) AS ename
    WHERE ename IS NOT NULL AND ename <> "" AND ename <> "\\"
    MERGE (en:结构工程 {名称: ename})
    MERGE (p)-[:结构工程设计]->(en)


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName,
        split(coalesce(row.施工, ""), "，") + split(coalesce(row.施工, ""), ",") AS builders
    WHERE projectName IS NOT NULL AND projectName <> ""

    MATCH (p:项目 {名称: projectName})
    UNWIND builders AS b
    WITH p, trim(b) AS bname
    WHERE bname IS NOT NULL AND bname <> "" AND bname <> "\\"
    MERGE (bu:施工 {名称: bname})
    MERGE (p)-[:施工方]->(bu)

    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName,
        split(coalesce(row.厂家, ""), "，") + split(coalesce(row.厂家, ""), ",") AS factories
    WHERE projectName IS NOT NULL AND projectName <> ""

    MATCH (p:项目 {名称: projectName})
    UNWIND factories AS f
    WITH p, trim(f) AS fname
    WHERE fname IS NOT NULL AND fname <> "" AND fname <> "\\"
    MERGE (fa:厂家 {名称: fname})
    MERGE (p)-[:厂家]->(fa)


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName,
        [row.建筑特色1, row.建筑特色2] AS features
    WHERE projectName IS NOT NULL AND projectName <> ""

    MATCH (p:项目 {名称: projectName})
    UNWIND features AS f
    WITH p, trim(f) AS fname
    WHERE fname IS NOT NULL AND fname <> "" AND fname <> "\\"
    MERGE (fe:建筑特色 {名称: fname})
    MERGE (p)-[:具有建筑特色]->(fe)




    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row

    WITH [trim(row.`建筑师团队1`), trim(row.`建筑师团队2`), trim(row.`建筑师团队3`), trim(row.`建筑师团队4`)] AS architects

    // 过滤空值
    WITH [a IN architects WHERE a IS NOT NULL AND a <> ''] AS valid_architects

    UNWIND valid_architects AS a1
    UNWIND valid_architects AS a2
    WITH a1, a2
    WHERE a1 <> a2  // 排除自己对自己

    // 建立正向
    MATCH (arch1:建筑师团队 {名称: a1})
    MATCH (arch2:建筑师团队 {名称: a2})
    MERGE (arch1)-[:COOPERATES_WITH]->(arch2);

    // 建立反向
    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row

    WITH [trim(row.`建筑师/团队1`), trim(row.`建筑师/团队2`), trim(row.`建筑师/团队3`), trim(row.`建筑师/团队4`)] AS architects
    WITH [a IN architects WHERE a IS NOT NULL AND a <> ''] AS valid_architects

    UNWIND valid_architects AS a1
    UNWIND valid_architects AS a2
    WITH a1, a2
    WHERE a1 <> a2

    MATCH (arch1:建筑师团队 {名称: a1})
    MATCH (arch2:建筑师团队 {名称: a2})
    MERGE (arch2)-[:COOPERATES_WITH]->(arch1);


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName, trim(row.高层) AS highRise
    WHERE projectName IS NOT NULL AND projectName <> "" AND highRise IS NOT NULL AND highRise <> "" AND highRise <> "\\"

    MATCH (p:项目 {名称: projectName})
    MERGE (h:高层 {名称: highRise})
    MERGE (p)-[:属于高层建筑]->(h)


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName, trim(row.大跨) AS longSpan
    WHERE projectName IS NOT NULL AND projectName <> "" AND longSpan IS NOT NULL AND longSpan <> "" AND longSpan <> "\\"

    MATCH (p:项目 {名称: projectName})
    MERGE (l:大跨 {名称: longSpan})
    MERGE (p)-[:属于大跨建筑]->(l)


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName, trim(row.层数) AS floors
    WHERE projectName IS NOT NULL AND projectName <> "" AND floors IS NOT NULL AND floors <> "" AND floors <> "\\"

    MATCH (p:项目 {名称: projectName})
    MERGE (f:层数 {名称: floors})
    MERGE (p)-[:具有层数]->(f)


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.项目名称) AS projectName, trim(row.状态) AS status
    WHERE projectName IS NOT NULL AND projectName <> "" AND status IS NOT NULL AND status <> "" AND status <> "\\"

    MATCH (p:项目 {名称: projectName})
    MERGE (s:建造状态 {名称: status})
    MERGE (p)-[:状态]->(s)


    LOAD CSV WITH HEADERS FROM 'file:///projects.csv' AS row
    WITH trim(row.城市) AS city, trim(row.国家) AS country
    WHERE city IS NOT NULL AND city <> "" AND country IS NOT NULL AND country <> ""

    MERGE (c:城市 {名称: city})
    MERGE (n:国家 {名称: country})
    MERGE (c)-[:属于国家]->(n)


    LOAD CSV WITH HEADERS FROM 'file:///其他材料.csv' AS row
    WITH trim(row.项目名称) AS projectName, trim(row.其他材料) AS material
    WHERE projectName IS NOT NULL AND projectName <> "" AND material IS NOT NULL AND material <> ""

    MATCH (p:项目 {名称: projectName})
    MERGE (m:其他材料 {名称: material})
    MERGE (p)-[:使用其他材料]->(m)

    LOAD CSV WITH HEADERS FROM 'file:///其他材料.csv' AS row
    WITH trim(row.其他材料) AS material, trim(row.构件) AS component
    WHERE material IS NOT NULL AND material <> "" AND component IS NOT NULL AND component <> ""

    MATCH (m:其他材料 {名称: material})
    MERGE (c:构件 {名称: component})
    MERGE (m)-[:used_in]->(c)

    LOAD CSV WITH HEADERS FROM 'file:///其他材料.csv' AS row
    WITH trim(row.其他材料) AS material, trim(row.材料特点) AS feature
    WHERE material IS NOT NULL AND material <> "" AND feature IS NOT NULL AND feature <> ""

    MATCH (m:其他材料 {名称: material})
    MERGE (f:材料特点 {描述: feature})
    MERGE (m)-[:具有材料特点]->(f)


    // 创建大跨木结构和高层木结构节点
    MERGE (b:结构类型 {名称: "大跨木结构"})
    MERGE (h:结构类型 {名称: "高层木结构"})

    // 将大跨木结构下的具体结构类型进行归类
    WITH b
    UNWIND ["实腹梁结构", "桁架结构", "拱结构", "刚架结构", "平板网架结构", "壳结构", "张弦结构"] AS structureType
    MERGE (s:结构类型 {名称: structureType})
    MERGE (b)-[:适合的结构类型]->(s)

    // 节点创建
    MERGE (h:结构类型 {名称: "高层木结构"})
    MERGE (p:结构类型 {名称: "纯木结构"})
    MERGE (m:结构类型 {名称: "木混合结构"})
    MERGE (um:结构类型 {名称: "上下木混合结构"})
    MERGE (cm:结构类型 {名称: "混凝土核心筒结构"})
    MERGE (p1:结构类型 {名称: "木框架剪力墙结构"})
    MERGE (p2:结构类型 {名称: "正交胶合木剪力墙结构"})
    MERGE (um1:结构类型 {名称: "上部木框架剪力墙结构"})
    MERGE (um2:结构类型 {名称: "上部正交胶合木剪力墙结构"})
    MERGE (f:结构类型 {名称: "纯框架结构"})
    MERGE (s:结构类型 {名称: "木框架支撑结构"})
    MERGE (s2:结构类型 {名称: "巨型木桁架结构"})

    // 架构层级关系

    // 高层木结构 -> 第一层两大体系
    MERGE (h)-[:包含结构类型]->(p)
    MERGE (h)-[:包含结构类型]->(m)

    // 纯木结构 -> 类型
    MERGE (p)-[:包含结构类型]->(p1)
    MERGE (p)-[:包含结构类型]->(p2)
    MERGE (p)-[:包含结构类型]->(s2)

    // 木混合结构 -> 细分体系
    MERGE (m)-[:包含结构类型]->(um)
    MERGE (m)-[:包含结构类型]->(cm)

    // 上下木混合结构 -> 类型
    MERGE (um)-[:包含结构类型]->(um1)
    MERGE (um)-[:包含结构类型]->(um2)

    // 混凝土核心筒结构 -> 类型
    MERGE (cm)-[:包含结构类型]->(f)
    MERGE (cm)-[:包含结构类型]->(s)
    MERGE (cm)-[:包含结构类型]->(p2) // 正交胶合木剪力墙结构也属于该体系


    MATCH (a:大跨), (b:结构类型)
    WHERE a.名称 = "大跨" AND b.名称 = "大跨木结构"
    MERGE (a)-[:等价]->(b)
    MERGE (b)-[:等价]->(a)

    MATCH (a:高层), (b:结构类型)
    WHERE a.名称 = "高层" AND b.名称 = "高层木结构"
    MERGE (a)-[:等价]->(b)
    MERGE (b)-[:等价]->(a)

    LOAD CSV WITH HEADERS FROM 'file:///结构类型定义.csv' AS row
    WITH trim(row.结构类型) AS structureType, trim(row.定义) AS definition
    WHERE structureType IS NOT NULL AND structureType <> "" AND definition IS NOT NULL AND definition <> ""

    MERGE (s:结构类型 {名称: structureType})
    SET s.定义 = definition


    LOAD CSV WITH HEADERS FROM 'file:///连接方式.csv' AS row
    WITH trim(row.项目) AS projectName, 
        trim(row.连接方式) AS connection, 
        trim(row.连接类型) AS connectionType
    WHERE projectName IS NOT NULL AND projectName <> "" 
    AND connection IS NOT NULL AND connection <> ""
    AND connectionType IS NOT NULL AND connectionType <> ""

    MERGE (p:项目 {名称: projectName})
    MERGE (c:连接方式 {名称: connection})
    MERGE (t:连接类型 {名称: connectionType})

    MERGE (p)-[:使用连接方式]->(c)
    MERGE (c)-[:属于连接类型]->(t)


    LOAD CSV WITH HEADERS FROM 'file:///连接类型定义.csv' AS row
    WITH trim(row.连接类型) AS connectionName, 
        trim(row.定义) AS definition
    WHERE connectionName IS NOT NULL AND connectionName <> "" 
    AND definition IS NOT NULL AND definition <> ""

    MERGE (c:连接类型 {名称: connectionName})
    SET c.定义 = definition


    LOAD CSV WITH HEADERS FROM 'file:///树种特性.csv' AS row
    WITH trim(row.树种1) AS treeType1, 
        trim(row.树种2) AS treeType2, 
        trim(row.树种特性) AS treeFeature, 
        trim(row.国家) AS country
    WHERE treeType1 <> "" AND treeType2 <> "" AND treeFeature <> "" AND country <> ""

    MERGE (t1:树种 {名称: treeType1})
    WITH t1, treeType2, treeFeature, country

    MERGE (t2:树种 {名称: treeType2})
    MERGE (t1)-[:包含树种]->(t2)
    WITH t2, treeFeature, country

    MERGE (f:树种特性 {描述: treeFeature})
    MERGE (t2)-[:具有树种特性]->(f)
    WITH t2, country

    MERGE (c:国家 {名称: country})
    MERGE (t2)-[:位于国家]->(c)



    LOAD CSV WITH HEADERS FROM 'file:///树种.csv' AS row
    WITH 
    trim(row.项目) AS projectName, 
    trim(row.树种) AS treeType, 
    trim(row.构件) AS component, 
    trim(row.树种特性) AS treeFeature
    WHERE projectName <> "" AND treeType <> ""

    MERGE (p:项目 {名称: projectName})
    MERGE (t:树种 {名称: treeType})
    MERGE (p)-[:使用树种]->(t)

    FOREACH (_ IN CASE WHEN component <> "" THEN [1] ELSE [] END |
    MERGE (c:构件 {名称: component})
    MERGE (t)-[:used_in]->(c)
    )

    FOREACH (_ IN CASE WHEN treeFeature <> "" THEN [1] ELSE [] END |
    MERGE (f:树种特性 {描述: treeFeature})
    MERGE (t)-[:具有树种特性]->(f)
    )



    LOAD CSV WITH HEADERS FROM 'file:///木材类型.csv' AS row
    WITH trim(row.木材类型) AS materialType, trim(row.项目) AS projectName
    MATCH (p:项目 {名称: projectName})
    MERGE (m:木材类型 {名称: materialType})
    MERGE (p)-[:使用木材类型]->(m)

    LOAD CSV WITH HEADERS FROM 'file:///木材类型.csv' AS row
    WITH trim(row.构件) AS component, trim(row.木材类型) AS materialType
    WHERE component IS NOT NULL AND component <> "" 
    MATCH (m:木材类型 {名称: materialType})
    MERGE (c:构件 {名称: component})
    MERGE (m)-[:used_in]->(c)


    LOAD CSV WITH HEADERS FROM 'file:///木材类型.csv' AS row
    WITH trim(row.树种) AS treeType, trim(row.木材类型) AS materialType
    WHERE treeType IS NOT NULL AND treeType <> "" 
    MATCH (m:木材类型 {名称: materialType})
    MERGE (t:树种 {名称: treeType})
    MERGE (m)-[:be_made_of]->(t)

    LOAD CSV WITH HEADERS FROM 'file:///木材类型.csv' AS row
    WITH trim(row.木材特点) AS materialFeature, trim(row.木材类型) AS materialType
    WHERE materialFeature IS NOT NULL AND materialFeature <> "" 
    MATCH (m:木材类型 {名称: materialType})
    MERGE (f:木材特点 {描述: materialFeature})
    MERGE (m)-[:具有木材特点]->(f)

    LOAD CSV WITH HEADERS FROM 'file:///木材特点.csv' AS row
    WITH trim(row.木材类型1) AS materialType1
    WHERE materialType1 IS NOT NULL AND materialType1 <> ""
    MERGE (m1:木材类型 {名称: materialType1})

    LOAD CSV WITH HEADERS FROM 'file:///木材特点.csv' AS row
    WITH trim(row.木材类型1) AS materialType1, trim(row.木材类型2) AS materialType2
    WHERE materialType1 IS NOT NULL AND materialType2 IS NOT NULL AND materialType1 <> "" AND materialType2 <> ""
    MERGE (m1:木材类型 {名称: materialType1})
    MERGE (m2:木材类型 {名称: materialType2})
    MERGE (m1)-[:包含木材类型]->(m2)

    LOAD CSV WITH HEADERS FROM 'file:///木材特点.csv' AS row
    WITH trim(row.木材类型2) AS materialType2, trim(row.木材类型3) AS materialType3
    WHERE materialType2 IS NOT NULL AND materialType3 IS NOT NULL AND materialType2 <> "" AND materialType3 <> ""
    MERGE (m2:木材类型 {名称: materialType2})
    MERGE (m3:木材类型 {名称: materialType3})
    MERGE (m2)-[:包含木材类型]->(m3)

    LOAD CSV WITH HEADERS FROM 'file:///木材特点.csv' AS row
    WITH trim(row.木材类型3) AS materialType3, trim(row.木材特点) AS materialFeature
    WHERE materialType3 IS NOT NULL AND materialFeature IS NOT NULL AND materialType3 <> "" AND materialFeature <> ""
    MERGE (m3:木材类型 {名称: materialType3})
    MERGE (f:木材特点 {描述: materialFeature})
    MERGE (m3)-[:具有木材特点]->(f)


    LOAD CSV WITH HEADERS FROM 'file:///木材特点.csv' AS row
    WITH trim(row.木材类型3) AS materialType3, trim(row.应用场景) AS applicationScene
    WHERE materialType3 IS NOT NULL AND applicationScene IS NOT NULL AND materialType3 <> "" AND applicationScene <> ""
    MERGE (m3:木材类型 {名称: materialType3})
    MERGE (a:应用场景 {描述: applicationScene})
    MERGE (m3)-[:应用场景]->(a)

    // 创建木材类型及其别名节点和关系
    MERGE (m1:木材类型 {名称: '层板胶合木(GLT)'})
    MERGE (al1:别名 {名称: 'glued laminated timber'})
    MERGE (m1)-[:具有别名]->(al1)

    MERGE (m2:木材类型 {名称: '正交胶合木(CLT)'})
    MERGE (al2:别名 {名称: 'cross-laminated timber'})
    MERGE (al3:别名 {名称: '交叉层压木'})
    MERGE (al4:别名 {名称: '交叉层压胶合木'})
    MERGE (al5:别名 {名称: '交叉层压木材'})
    MERGE (al6:别名 {名称: 'Cross-Laminated Panels'})
    MERGE (m2)-[:具有别名]->(al2)
    MERGE (m2)-[:具有别名]->(al3)
    MERGE (m2)-[:具有别名]->(al4)
    MERGE (m2)-[:具有别名]->(al5)
    MERGE (m2)-[:具有别名]->(al6)

    MERGE (m3:木材类型 {名称: '层板钉合木(NLT)'})
    MERGE (al7:别名 {名称: 'nail laminated timber'})
    MERGE (m3)-[:具有别名]->(al7)

    MERGE (m4:木材类型 {名称: '销钉层压木材(DLT)'})
    MERGE (al8:别名 {名称: 'dowel-laminated timber'})
    MERGE (m4)-[:具有别名]->(al8)

    MERGE (m5:木材类型 {名称: '旋切板胶合木(LVL)'})
    MERGE (al9:别名 {名称: 'laminated veneer lumber'})
    MERGE (al10:别名 {名称: '单板层积材'})
    MERGE (al11:别名 {名称: '旋切单板胶合木'})
    MERGE (al12:别名 {名称: '单板层压木'})
    MERGE (m5)-[:具有别名]->(al9)
    MERGE (m5)-[:具有别名]->(al10)
    MERGE (m5)-[:具有别名]->(al11)
    MERGE (m5)-[:具有别名]->(al12)

    MERGE (m6:木材类型 {名称: '平行木片胶合木(PSL)'})
    MERGE (al13:别名 {名称: 'parallel strand lumber'})
    MERGE (m6)-[:具有别名]->(al13)

    MERGE (m7:木材类型 {名称: '层叠木片胶合木(LSL)'})
    MERGE (al14:别名 {名称: 'laminated strand lumber'})
    MERGE (m7)-[:具有别名]->(al14)

    MERGE (m8:木材类型 {名称: '定向木片胶合木(OSL)'})
    MERGE (al15:别名 {名称: 'oriented strand lumber'})
    MERGE (m8)-[:具有别名]->(al15)

    MERGE (m9:木材类型 {名称: '结构胶合板(SP)'})
    MERGE (al16:别名 {名称: 'structure plywood'})
    MERGE (m9)-[:具有别名]->(al16)

    MERGE (m10:木材类型 {名称: '定向木板片(OSB)'})
    MERGE (al17:别名 {名称: 'oriented strand board'})
    MERGE (al18:别名 {名称: '定向刨花板'})
    MERGE (al19:别名 {名称: '刨花板'})
    MERGE (m10)-[:具有别名]->(al17)
    MERGE (m10)-[:具有别名]->(al18)
    MERGE (m10)-[:具有别名]->(al19)
    """

def old_system_prompt(relevant_info):
    return f"""
        您是一名木结构建筑知识图谱查询助手，能够根据示例Cypher查询生成Cypher查询。 
        示例Cypher查询有：\n {example()} \n       
        下面是一些相关的背景知识请，仔细阅读，生成Cypher语句时需要结合：\n {background_knowledge(relevant_info)} \n
        除了Cypher查询之外，不要回复任何解释或任何其他信息。
        现在请为这个查询生成Cypher:
        # {relevant_info['question']}
        """
    # return f"""
    #     您是一名木结构建筑知识图谱查询助手，能够根据示例Cypher查询生成Cypher查询。
    #     示例Cypher查询有：\n {example()} \n
    #     数据库的构建过程如下，请仔细查看里面的node和relationship，property keys。在生成cypher查询时要与这些里面的变量名都保持一致：{construct_db_cypher()} \n
    #     下面是一些相关的背景知识请，仔细阅读，生成Cypher语句时需要结合：\n {background_knowledge(relevant_info)} \n
    #     除了Cypher查询之外，不要回复任何解释或任何其他信息。
    #     您永远不要为你的不准确回复感到抱歉，并严格根据提供的cypher示例生成cypher语句。
    #     不要提供任何无法从Cypher示例中推断出的Cypher语句。
    #     当由于缺少对话上下文而无法推断密码语句时，通知用户，并说明缺少的上下文是什么。
    #     现在请为这个查询生成Cypher:
    #     # {relevant_info['question']}
    #     """
def old_prompt(relevant_info):
        prompt = old_system_prompt(relevant_info)
        return prompt

def example():
    return """
        # 查询功能为办公的项目：
        MATCH (p:项目)-->(f:功能 {名称: '办公'}) RETURN p
        
        # 查询国家为中国的项目：
        MATCH (p:项目)-->(c:国家 {名称: '中国'}) RETURN p
        
        # 查询结构类型为钢结构：
        MATCH (p:项目)-->(s:结构类型 {名称: '钢结构'}) RETURN p
        
        # 查询建成年份为202的项目：
        MATCH (p:项目)-->(y:建成年份 {名称: '2020'}) RETURN p
        
        # 查询建筑师团队为abba：
        MATCH (p:项目)-->(a:建筑师团队 {名称: 'abba'}) RETURN p
        
        # 查询项目及其所有关联信息：
        MATCH (p:项目)-[r]-(n) RETURN p, r, n
        
        # 查询城市名称为北京的项目：
        MATCH (p:项目)-->(c:城市 {名称: '北京'}) RETURN p
        
        # 查询面积分级为大型的项目：
        MATCH (p:项目)-->(a:面积分级 {名称: '大型'}) RETURN p
        
        # 查询有某属性的项目：
        MATCH (p:项目) WHERE p.高层 IS NOT NULL RETURN p
        
        # 查询层数大于10的项目：
        MATCH (p:项目) WHERE toInteger(p.层数) > 10 RETURN p
        
        # 查询建筑面积大于10000的项目：
        MATCH (p:项目) WHERE toInteger(p.建筑面积) > 10000 RETURN p
        
        # 查询使用树种为松木的项目：
        MATCH (p:项目)-->(t:树种 {名称: '松木'}) RETURN p
        
        # 查询使用木材类型为CLT的项目：
        MATCH (p:项目)-->(m:木材类型 {名称: 'CLT'}) RETURN p
        
        # 查询连接方式为榫卯连接的项目：
        MATCH (p:项目)-->(c:连接方式 {名称: '榫卯连接'}) RETURN p
        
        # 查询结构类型的层次关系：
        MATCH (s1:结构类型)-->(s2:结构类型) RETURN s1, s2
        
        # 查询木材类型的别名：
        MATCH (m:木材类型)-[:具有别名]->(a:别名) RETURN m, a
        
        # 查询特定构件的使用情况：
        MATCH (m)-[:used_in]->(c:构件 {名称: '梁'}) RETURN m, c
        
        # 查询特定应用场景的木材类型：
        MATCH (m:木材类型)-->(a:应用场景 {描述: '结构构件'}) RETURN m, a

        # 查询使用CLT且层数大于5的项目：
        MATCH (p:项目)-->(m:木材类型 {名称: '正交胶合木(CLT)'})
            WHERE toInteger(p.层数) > 5
            RETURN p

        # 查询大跨木结构下的所有具体结构类型：
        MATCH (s1:结构类型 {名称: '大跨木结构'})-[:包含]->(s2:结构类型)
            RETURN s2

        # 查询特定树种的所有特性：
        MATCH (t:树种 {名称: '松木'})-[:树种特性]->(f:树种特性)
            RETURN t, f

        # 查询使用特定连接方式的高层项目：
        MATCH (p:项目)-->(c:连接方式 {名称: '榫卯连接'})
            WHERE p.高层 IS NOT NULL
            RETURN p, c

        # 查找有高层属性的所有项目:
        MATCH (p:项目) WHERE p.高层 IS NOT NULL RETURN p
        
        # 查询所有层数大于10的项目:
        MATCH (p:项目) WHERE toInteger(p.层数) > 10 RETURN p
        
        # 查找使用CLT的项目:
        MATCH (p:项目)-->(m:木材类型 {名称: '正交胶合木(CLT)'}) RETURN p
        
        # 查询大跨木结构的所有子类型:
        Cypher：MATCH (s1:结构类型 {名称: '大跨木结构'})-[:包含]->(s2:结构类型) RETURN s2
        
        # 查找壳结构的大跨项目:
        Cypher：MATCH (p:项目)-->(m:结构类型 {名称: '壳结构'}) WHERE p.大跨 IS NOT NULL RETURN p

    """
def deduplicate_dicts(dict_list):
    seen = set()
    result = []
    for d in dict_list:
        # 将字典转为可哈希的元组
        d_tuple = tuple(sorted(d.items()))
        if d_tuple not in seen:
            seen.add(d_tuple)
            result.append(d)
    return result

# 输出: [{'a': 1}, {'b': 2}]
def context_aware_kg_qa(question):
    """
    同步方式：结合Neo4j知识图谱和历史上下文，生成大模型回答
    """
    # 1. 获取对话上下文
    # conversation_context = qa_system.get_context_summary()
    # graph_context = qa_system.get_graph_context()

    # 2. 基于关键词查询图谱
    # relevant_info = get_relevant_nodes_and_relations(
    #      prompt, GRAPH_CONFIG['allowed_nodes'], GRAPH_CONFIG['allowed_relationships'], GRAPH_CONFIG['allowed_properties']
    # )
    relevant_info={"question":question,
                   **GRAPH_CONFIG}
    # cypher_query = build_dynamic_cypher_query(relevant_info, prompt)
    # cypher_query = ensure_cypher_limit(cypher_query, limit=20)
    # try:
    #     query_result = graph.run(cypher_query).data()
    # except Exception as e:
    #     query_result = [f"Cypher查询失败: {str(e)}"]

    # 3. 构造大模型输入
    prompt = old_prompt(relevant_info)
    fuzzy_nodes = GRAPH_CONFIG["fuzzy_words"]
    jieba_words = GRAPH_CONFIG["jieba_words"]
    for word in jieba_words:
        jieba.add_word(word, freq=10000)
    keywords = jieba.lcut(question)
    key_terms = [word for word in keywords if len(word) >= 2]
    
    # messages += history
    # messages.append({"role": "user", "content": prompt})
    ##功能 木材类型 树种 建筑特色 连接方式 建筑师团队 结构类型(模糊查询)
    
    fuzzy_idx, fuzzy_key, fuzzy_value = None, None, None
    for idx,kv  in enumerate(key_terms[:-1]):
        if kv in fuzzy_nodes:
            fuzzy_key=kv
            fuzzy_idx=idx
            break
    if fuzzy_idx!=None:
        fuzzy_value = key_terms[fuzzy_idx+1]
    # # 4. 构造历史消息
    # fuzzy_methods = ["CONTAINS", "STARTS WITH","ENDS WITH","REGEX"]
    # fuzzy_methods = ["CONTAINS", "STARTS WITH","ENDS WITH"]
    fuzzy_methods = ["CONTAINS"]
    fuzzy_examples=[]
    if fuzzy_value!=None:
        fuzzy_examples = fuzzy_fun(fuzzy_key,fuzzy_value,fuzzy_methods)
        

    messages = [{"role": "user", "content": prompt}]
    # 5. 调用大模型
    client = get_api_client()
    response = client.chat.completions.create(
        model=LLM_CONFIG["Model"],
        messages=messages,
        max_tokens=200,  # 适中的长度
        temperature=0.3,  # 降低随机性，提高速度
        stream=True
    )

    placeholder = st.empty()  # 创建占位区域
    # placeholder.markdown("Cypher查询语句：")
    full_response = ""
    for chunk in response:
        content = chunk.choices[0].delta.content or ""
        full_response += content
        # placeholder.markdown(full_response)  # 实时更新占位区域
    
    full_response_list = []
    if full_response.strip() != "" and len(fuzzy_examples)>0:
        full_response_list.append(full_response)
        for fuzz_method,fuzz_exp in zip(fuzzy_methods,fuzzy_examples):
            fuzzy_prompt=get_fuzzy_prompt(question,full_response,fuzz_method,fuzz_exp)
            messages = [{"role": "user", "content": fuzzy_prompt}]
            response = client.chat.completions.create(
            model=LLM_CONFIG["Model"],
            messages=messages,
            max_tokens=200,  # 适中的长度
            temperature=0.3,  # 降低随机性，提高速度
            stream=True
        )
            placeholder = st.empty()  # 创建占位区域
            # placeholder.markdown("Cypher查询语句：")
            full_response = ""
            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                full_response += content
                # placeholder.markdown(full_response)  # 实时更新占位区域
            full_response_list.append(full_response)
        if len(full_response_list)==2:
            last_response = full_response_list[-1]
            regex_response = last_response.replace('CONTAINS','STARTS WITH')
            full_response_list.append(regex_response)
            regex_response = last_response.replace('CONTAINS','ENDS WITH')
            full_response_list.append(regex_response)

        if len(full_response_list)==4:
            last_response = full_response_list[-1]
            regex_response = last_response.split('ENDS WITH')[0] +  f" =~ '(?i).*{fuzzy_value}.*$' RETURN p"
            full_response_list.append(regex_response)
        return full_response_list
    else:
        return full_response.strip()

def get_fuzzy_prompt(question,full_response,fuzz_method,fuzz_exp):
    text = f""""
    请使用{fuzz_method}，来针对问题:{question}生成的查询语句:{full_response}重新生成一个支持该方法模糊查询的cypher语句，请严格参考下面的模糊查询例子的格式，尤其是regex方式:\n
    {fuzz_exp} \n
    注意，新生成的cypher语句会直接用于neo4j数据库的查询，请不要输出其它无关内容，直接输出cypher query语句。
    """
    return text

def fuzzy_fun(fuzzy_key,fuzzy_value,fuzzy_methods):
    
    fuzzy_prompt_list = []
    for fz in fuzzy_methods:
        if fz == "CONTAINS":
            text = f"""
            #使用{fz}来模糊查询{fuzzy_key}为{fuzzy_value}的项目：
            MATCH (p:项目)-->(m:{fuzzy_key})
            WHERE toLower(m.名称) {fz} toLower('{fuzzy_value}')
            RETURN p
        """
            fuzzy_prompt_list.append(text)
        elif fz == "STARTS WITH":
            text = f"""
            #使用{fz}来模糊查询{fuzzy_key}为{fuzzy_value}的项目：
            MATCH (p:项目)-->(m:{fuzzy_key})
            WHERE toLower(m.名称) {fz} toLower('{fuzzy_value}')
            RETURN p
        """
            fuzzy_prompt_list.append(text)
        elif fz == "ENDS WITH":
            text = f"""
            #使用{fz}来模糊查询{fuzzy_key}为{fuzzy_value}的项目：
            MATCH (p:项目)-->(m:{fuzzy_key})
            WHERE toLower(m.名称) {fz} toLower('{fuzzy_value}')
            RETURN p
        """
            fuzzy_prompt_list.append(text)
        elif fz == "REGEX":
            text = f"""
            #使用{fz}来模糊查询{fuzzy_key}为{fuzzy_value}的项目：
            MATCH (p:项目)-->(m:{fuzzy_key})
            WHERE m.名称 =~ '(?i).*{fuzzy_value}.*' 
            RETURN p
        """
            fuzzy_prompt_list.append(text)
    return fuzzy_prompt_list
# 在文件顶部或 context_aware_kg_qa 前定义 schema 变量：

def background_knowledge(relevant_info):
    return f'''
你正在访问的木结构建筑知识图谱，包含以下完整结构：\n
Graph中真实存在的节点，关系以及属性信息如下，生成的cypher语句务必于下面信息一直，即真实有效：
allowed_nodes： { GRAPH_CONFIG['allowed_nodes']}
allowed_relationships： { GRAPH_CONFIG['allowed_relationships']}
allowed_properties： {GRAPH_CONFIG['allowed_properties']}
'''
