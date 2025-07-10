import networkx as nx
import plotly.graph_objects as go
from typing import Dict, Any
import json
from data_persistence_utils import get_cache_dir
import os
import logging
import colorsys
import re
import jieba
import jieba.analyse
from neo4j import GraphDatabase
from config import NEO4J_CONFIG

# 加载图谱数据
def load_graph_from_json(file_hash: str) -> nx.Graph:
    cache_file = os.path.join(get_cache_dir(), f"{file_hash}_graph_data.json")
    print(f"Attempting to load graph data from: {cache_file}")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            G = nx.Graph()

            # 添加节点
            for node in data['nodes']:
                G.add_node(node['id'], type=node['type'], **node['properties'])

            # 修改关系处理部分
            for rel in data['relationships']:
                try:
                    # 直接使用 source 和 target
                    source_id = rel['source'] if isinstance(rel['source'], str) else str(rel['source'])
                    target_id = rel['target'] if isinstance(rel['target'], str) else str(rel['target'])

                    # 如果还是包含 id 标记，则尝试提取
                    if "id='" in source_id:
                        source_id = re.search(r"id='([^']*)'", source_id)
                        source_id = source_id.group(1) if source_id else source_id
                    if "id='" in target_id:
                        target_id = re.search(r"id='([^']*)'", target_id)
                        target_id = target_id.group(1) if target_id else target_id

                    # 添加边
                    G.add_edge(source_id, target_id, label=rel['type'], **rel['properties'])
                except Exception as e:
                    print(f"Warning: Could not add relationship: {rel}. Error: {str(e)}")
                    continue

            print(f"Successfully loaded graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
            return G
        except Exception as e:
            print(f"Error loading graph data: {str(e)}")
            logging.exception("Error details:")
    else:
        print(f"File not found: {cache_file}")
    return None

# 获取相关节点和关系
def get_relevant_nodes_and_relations(graph, question, allowed_nodes, allowed_relationships):
    # 1. 对问题进行分词
    keywords = jieba.lcut(question)
    key_terms = [word for word in keywords if len(word) >= 2]  # 只保留长度>=2的词

    # 2. 查找包含关键词的相关节点
    relevant_nodes = []
    for node in allowed_nodes:
        if any(term.lower() in node.lower() for term in key_terms):
            relevant_nodes.append(node)

    # 3. 查找相关的关系
    relevant_relations = []
    for relation in allowed_relationships:
        if any(term.lower() in relation.lower() for term in key_terms):
            relevant_relations.append(relation)

    return {
        "nodes": relevant_nodes,
        "relations": relevant_relations
    }

# 构建动态Cypher查询
def build_dynamic_cypher_query(relevant_info: Dict[str, Any], question: str) -> str:
    """构建动态Cypher查询"""
    nodes = relevant_info.get("nodes", [])
    relations = relevant_info.get("relations", [])
    keywords = relevant_info.get("keywords", [])
    
    # 构建关键词匹配条件
    keyword_conditions = []
    for keyword in keywords[:5]:  # 限制关键词数量
        keyword_conditions.append(f"n.text CONTAINS '{keyword}'")
        keyword_conditions.append(f"n.id CONTAINS '{keyword}'")
        keyword_conditions.append(f"n.name CONTAINS '{keyword}'")
        keyword_conditions.append(f"n.名称 CONTAINS '{keyword}'")
    
    keyword_match = " OR ".join(keyword_conditions) if keyword_conditions else "1=1"
    
    # 主要查询：基于关键词匹配
    main_query = f"""
    MATCH (n)
    WHERE {keyword_match}
    WITH n
    ORDER BY size(n.text) DESC
    LIMIT 10
    OPTIONAL MATCH (n)-[r]-(related)
    WITH n, r, related
    """
    
    # 过滤条件
    filter_conditions = []
    if nodes:
        node_filter = " OR ".join([f"'{node}' IN labels(n) OR '{node}' IN labels(related)" for node in nodes])
        filter_conditions.append(f"({node_filter})")
    if relations:
        relation_filter = " OR ".join([f"type(r) = '{rel}'" for rel in relations])
        filter_conditions.append(f"({relation_filter})")
    
    filter_query = " AND ".join(filter_conditions)
    if filter_query:
        filter_query = f"WHERE {filter_query}"
    
    # 返回结果
    return_query = """
    RETURN DISTINCT n, r, related
    ORDER BY n.text
    LIMIT 50
    """
    
    full_query = main_query + filter_query + return_query
    return full_query

def get_neo4j_driver():
    return GraphDatabase.driver(
        NEO4J_CONFIG["uri"],
        auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"])
    )

def get_graph_overview(limit=100):
    """
    获取部分节点和边，用于前端可视化
    """
    driver = get_neo4j_driver()
    with driver.session() as session:
        nodes = session.run("MATCH (n) RETURN n LIMIT $limit", limit=limit)
        edges = session.run("MATCH (n)-[r]->(m) RETURN n, r, m LIMIT $limit", limit=limit)
        node_list = []
        edge_list = []
        node_ids = set()
        for record in nodes:
            n = record["n"]
            node_list.append({
                "id": n.id,
                "labels": list(n.labels),
                "properties": dict(n)
            })
            node_ids.add(n.id)
        for record in edges:
            n = record["n"]
            m = record["m"]
            r = record["r"]
            edge_list.append({
                "source": n.id,
                "target": m.id,
                "type": r.type,
                "properties": dict(r)
            })
            if n.id not in node_ids:
                node_list.append({
                    "id": n.id,
                    "labels": list(n.labels),
                    "properties": dict(n)
                })
                node_ids.add(n.id)
            if m.id not in node_ids:
                node_list.append({
                    "id": m.id,
                    "labels": list(m.labels),
                    "properties": dict(m)
                })
                node_ids.add(m.id)
        return {"nodes": node_list, "edges": edge_list}

def search_nodes_by_name(name, limit=20):
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (n) WHERE n.name CONTAINS $name RETURN n LIMIT $limit",
            name=name, limit=limit
        )
        return [
            {"id": record["n"].id, "labels": list(record["n"].labels), "properties": dict(record["n"])}
            for record in result
        ]
