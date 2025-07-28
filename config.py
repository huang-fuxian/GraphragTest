# config.py


# from dotenv import load_dotenv

# # 加载环境变量
# load_dotenv()

# API配置
# LLM_CONFIG = {
#     'API_KEY':"sk-dlkclqnhiisoienmsmznzwaufudgbpqxlggsyfgzgefiogks",
#     "API_URL": "https://api.siliconflow.cn/v1" ,
#     # "Model": "deepseek-ai/DeepSeek-R1"
#     "Model": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
#     # "Model": "THUDM/glm-4-9b-chat"
# }
LLM_CONFIG = {
    'API_KEY':"sk-b89dee029855435b8452c2f52d3bdb08",
    "API_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1" ,
    # "Model": "deepseek-r1"，
    # "Model": "qwen-plus"，
    "Model":"qwen-turbo"    
}



# Neo4j配置 - 请在这里设置您的Neo4j密码
NEO4J_CONFIG = {"DB1":{
    "uri": "bolt://localhost:7687",
    "user": "neo4j",
    "password": "test123456"  # 您的Neo4j密码
},
"DB2":{
    "uri": "bolt://localhost:7687",
    "user": "neo4j",
    "password": "test123456"  # 您的Neo4j密码
},
}

# 本地嵌入配置
EMBEDDING_CONFIG = {
    'local': {
        'base_url': "http://localhost:1234/v1",
        'model': "BAAI/BAAI_bge-large-zh-v1.5/bge-large-zh-v1.5-f32.gguf"
    }
}

GRAPH_CONFIG = {
    "fuzzy_words":["功能", "木材类型", "树种", "建筑特色", "连接方式", "建筑师团队", "结构类型"],
    "jieba_words":["功能", "木材类型", "树种", "建筑特色", "连接方式", "建筑师团队", "结构类型","隈研吾","壳结构"],
    'allowed_nodes': [
        '别名',
'材料特点',
'层数',
'厂家',
'城市',
'大跨',
'高层',
'功能',
'构件',
'国家',
'建成年份',
'建造状态',
'建筑师团队',
'建筑特色',
'结构工程',
'结构类型',
'连接方式',
'连接类型',
'面积分级',
'木材类型',
'木材特点',
'其他材料',
'施工',
'树种',
'树种特性',
'项目',
'应用场景',
    ],
'allowed_relationships': [
'包含结构类型', 
'包含木材类型', 
'包含树种', 
'采用结构类型', 
'厂家', 
'等价', 
'建成时间', 
'结构工程设计', 
'具有别名', 
'具有材料特点', 
'具有层数', 
'具有建筑功能', 
'具有建筑特色', 
'具有木材特点', 
'具有树种特性', 
'施工方', 
'使用连接方式', 
'使用木材类型', 
'使用其他材料', 
'使用树种', 
'适合的结构类型', 
'属于大跨建筑', 
'属于高层建筑', 
'属于国家', 
'属于连接类型', 
'属于面积分级', 
'位于城市', 
'位于国家', 
'应用场景', 
'由建筑师团队设计', 
'状态', 
        # "国家", "城市",  "建筑特色", "厂家",
        # "面积分级", "建成年份", "施工",  "结构工程",
        # "结构类型" 
    ],
    'allowed_properties':[
        # "名称","图片","大跨","层数","建筑面积","状态","跨度","链接","高层","高度","data","id","name","nodes","relationships","style","visualisation"
        '层数',
'大跨',
'定义',
'分类标准',
'高层',
'高度',
'建筑面积',
'跨度',
'链接',
'描述',
'名称',
'图片',
'状态',
'data',
'id',
'name',
'nodes',
'relationships',
'style',
'visualisation',
        ]
    # 'allowed_properties':["名称","图片","大跨","层数","建筑面积","状态","跨度","链接","高层","高度","data","id","name","nodes","relationships","style","visualisation"]
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
