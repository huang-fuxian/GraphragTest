# config.py

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# API配置
LLM_CONFIG = {
    'API_KEY':"sk-icchogndqscnbeniasywjjmyukqsyxfnewjiiuioqglwejmc",
    "API_URL": "https://api.siliconflow.cn/v1" ,
    "Model": "THUDM/glm-4-9b-chat"
}

# Neo4j配置 - 请在这里设置您的Neo4j密码
NEO4J_CONFIG = {
    "uri": "bolt://localhost:7687",
    "user": "neo4j",
    "password": "test123456"  # 您的Neo4j密码
}

# 本地嵌入配置
EMBEDDING_CONFIG = {
    'local': {
        'base_url': "http://localhost:1234/v1",
        'model': "BAAI/BAAI_bge-large-zh-v1.5/bge-large-zh-v1.5-f32.gguf"
    }
}

GRAPH_CONFIG = {
    'allowed_nodes': [
        "功能", "厂家", "国家", "城市", "建成年份",
        "建筑师团队", "建筑特色", "施工", "研究内容", "结构工程",
        "结构类型", "连接方式", "面积分级", "项目"
    ],
    'allowed_relationships': [
        "功能", "厂家", "国家", "城市", "建成年份",
        "建筑师团队", "建筑特色", "施工", "状态", "结构工程",
        "结构类型", "连接方式", "面积分级"
    ]
}

# 文档处理配置
DOC_CONFIG = {
    'chunk_size': 1000,
    'chunk_overlap': 40
}

# 应用配置
APP_CONFIG = {
    'title': "DateGraphX：实时图谱RAG应用",
    'description': """
    此应用程序允许您上传PDF文件，将其内容提取到Neo4j图形数据库中，并使用自然语言执行查询。
    它利用LangChain和DeepSeek的模型生成Cypher查询，实时与Neo4j数据库交互。
    """,
    'logo_path': 'logo.png'
}
