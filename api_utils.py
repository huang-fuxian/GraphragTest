# api_utils.py


from openai import OpenAI 
from config import LLM_CONFIG, EMBEDDING_CONFIG, NEO4J_CONFIG
from neo4j import GraphDatabase

def get_api_client(api_type: str, api_key: str, model_name: str) -> OpenAI:
    """获取API客户端"""
    base_url = API_CONFIG[api_type.lower()]['base_url']
    return OpenAI(api_key=api_key, base_url=base_url)

def get_context_aware_response(question: str, history: list, api_type: str, api_key: str, model_name: str, max_tokens: int = 512) -> str:
    """
    简单上下文感知问答示例
    """
    client = get_api_client(api_type, api_key, model_name)
    messages = history + [{"role": "user", "content": question}]
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=max_tokens
    )
    return clean_api_response(response.choices[0].message.content, api_type)

def get_context_aware_response_stream(question: str, history: list, client,  model_name: str, max_tokens: int = 512):
    """
    支持流式输出的上下文感知问答
    """
    
    messages = history + [{"role": "user", "content": question}]
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=max_tokens,
        stream=True
    )
    for chunk in response:
        delta = getattr(chunk.choices[0], 'delta', None)
        if delta and getattr(delta, 'content', None):
            yield delta.content

def query_knowledge_graph(question: str) -> str:
    """
    根据问题在 Neo4j 知识图谱中检索相关节点（按名称模糊查找）
    """
    driver = GraphDatabase.driver(
        NEO4J_CONFIG["uri"],
        auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"])
    )
    with driver.session() as session:
        cypher = "MATCH (n) WHERE n.name CONTAINS $question RETURN n LIMIT 5"
        result = session.run(cypher, question=question)
        nodes = [record["n"] for record in result]
        if not nodes:
            return "知识图谱中未找到相关内容。"
        return "\n".join([str(dict(node)) for node in nodes])