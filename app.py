from flask import Flask, render_template, request, jsonify
import requests
from openai import OpenAI
from langchain.prompts import ChatPromptTemplate
from utils import context_aware_kg_qa,extract_cypher_from_llm_output,configure_neo4j,graph_rag_fun,simple_extract_cypher
from config import LLM_CONFIG
app = Flask(__name__)
API_KEY = LLM_CONFIG["API_KEY"]
LLM_API_URL = LLM_CONFIG["API_URL"]
Model_name = LLM_CONFIG["Model"]

def call_llm_model(prompt):
    client = OpenAI(api_key=API_KEY, base_url=LLM_API_URL)
    
    # 发送请求到模型
    response = client.chat.completions.create(
        model=Model_name,
        messages=[
            {'role': 'user', 
                'content': f"{prompt}"}  # 用户输入的提示
        ],
    )

    # 打印响应结构，以便调试
    # print("Response structure:", response)

    # 收集所有响应内容
    content = ""
    if hasattr(response, 'choices') and response.choices:
        for choice in response.choices:
            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                chunk_content = choice.message.content
                # print(chunk_content, end='')  # 可选：打印内容
                content += chunk_content  # 将内容累加到总内容中
    else:
        raise ValueError("Unexpected response structure")
    return content



@app.route('/')
def home():
    return render_template('index.html')  # 渲染输入页面

@app.route('/ask', methods=['POST'])
def ask():
    user_input = request.json.get('question', '')
    if not user_input:
        return jsonify({"answer": "问题不能为空"}), 400
    
    
    graph = configure_neo4j()
    response = context_aware_kg_qa(user_input)
    cypher_query = simple_extract_cypher(response)
    if cypher_query: 
        print(f"📝 查看Cypher查询语句:{cypher_query}")
        search_result, full_stream_text = graph_rag_fun(cypher_query,graph,user_input)
        if full_stream_text==None:
            answer = call_llm_model(user_input)   
        else:
            answer = full_stream_text
    else:
        answer = call_llm_model(user_input) 

    return jsonify({"answer": answer})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)