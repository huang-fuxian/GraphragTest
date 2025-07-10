# api_utils.py

from typing import List, Tuple, Optional
import requests
from openai import OpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.embeddings.base import Embeddings
from llm.config import API_CONFIG, EMBEDDING_CONFIG, NEO4J_CONFIG
from neo4j import GraphDatabase

class LocalEmbeddings(Embeddings):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        url = f"{self.base_url}/embeddings"
        embeddings = []
        for text in texts:
            response = requests.post(url, json={"input": text, "model": self.model})
            embeddings.append(response.json()["data"][0]["embedding"])
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        url = f"{self.base_url}/embeddings"
        response = requests.post(url, json={"input": text, "model": self.model})
        return response.json()["data"][0]["embedding"]

def clean_api_response(response: str, api_type: str) -> str:
    """清理API响应"""
    # if api_type == "DeepSeek":
    #     return response.replace("", "").strip()
    return response.strip()

def test_api_connection(api_type: str, api_key: str, model_name: str) -> Tuple[bool, str]:
    """测试API连接"""
    try:
        base_url = API_CONFIG[api_type.lower()]['base_url']
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hi!"}],
            max_tokens=10
        )
        raw_response = response.choices[0].message.content
        cleaned_response = clean_api_response(raw_response, api_type)
        return True, cleaned_response
    except Exception as e:
        return False, str(e)

def test_embeddings(embed_type: str, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None) -> Tuple[bool, str]:
    """测试嵌入模型"""
    try:
        if embed_type == "本地":
            embeddings = LocalEmbeddings(
                base_url=base_url or EMBEDDING_CONFIG['local']['base_url'],
                model=model or EMBEDDING_CONFIG['local']['model']
            )
        else:
            embeddings = OpenAIEmbeddings(api_key=api_key)
        
        test_embedding = embeddings.embed_query("test")
        return True, f"成功生成嵌入向量，维度: {len(test_embedding)}"
    except Exception as e:
        return False, str(e)

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

def get_context_aware_response_stream(question: str, history: list, api_type: str, api_key: str, model_name: str, max_tokens: int = 512):
    """
    支持流式输出的上下文感知问答
    """
    client = get_api_client(api_type, api_key, model_name)
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