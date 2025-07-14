import json
import streamlit as st  
from openai import OpenAI   
from utils import context_aware_kg_qa,extract_cypher_from_llm_output,configure_neo4j,graph_rag_fun,simple_extract_cypher
from config import LLM_CONFIG

API_KEY = LLM_CONFIG["API_KEY"]
LLM_API_URL = LLM_CONFIG["API_URL"]
Model_name = LLM_CONFIG["Model"]
# 设置页面标题  
st.set_page_config(
    layout="wide", 
    page_title="DataGraphX - 木结构建筑知识图谱问答系统", 
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)
# 将用户输入框移动到顶部（标题下方）
# if prompt := st.chat_input("在这里输入您的问题..."):  
#     st.session_state.messages.append({"role": "user", "content": prompt})
    # 处理用户输入的代码将保持在这里...
# 在侧边栏添加配置选项  
with st.sidebar:  
    # 提供一个文本输入框让用户可以手动输入API Key（可选）  
    # openai_api_key = st.text_input("DeepSeek API Key", key="chatbot_api_key", type="password")  
    # "[获取 DeepSeek API key](https://platform.deepseek.com/api_keys)"  
    if st.button("开启新对话"):  
        if "messages" in st.session_state and len(st.session_state.messages) > 0:  
            # 保存当前对话到历史对话列表  
            if "history_conversations" not in st.session_state:  
                st.session_state.history_conversations = []  
            st.session_state.history_conversations.append(st.session_state.messages)  
            st.session_state.messages = [{"role": "assistant", "content": "欢迎使用对话机器人，你想知道什么?"}]  
  
  
    # 显示历史对话列表  
    st.subheader("历史对话")  
    if "history_conversations" in st.session_state:  
        for idx, conv in enumerate(st.session_state.history_conversations):  
            if st.button(f"对话 {idx + 1}", key=f"load_conv_{idx}"):  
                st.session_state.messages = conv  
                # st.success(f"成功加载对话 {idx + 1}")  


client = OpenAI(api_key=API_KEY, base_url=LLM_API_URL)  

# 初始化对话历史记录  
if "messages" not in st.session_state:  
    st.session_state.messages = [{"role": "assistant", "content": "欢迎使用对话机器人，你想知道什么?"}]  

# 显示对话历史  
for msg in st.session_state.messages:  
    st.chat_message(msg["role"]).write(msg["content"])  

# 获取用户输入  
if prompt := st.chat_input():  
    st.session_state.messages.append({"role": "user", "content": prompt})  
    st.chat_message("user").write(prompt)  


    graph = configure_neo4j()
    response = context_aware_kg_qa(prompt)
    cypher_query = simple_extract_cypher(response)
    full_stream_text = None
    search_result = None
    if cypher_query: 
        print(f"📝 查看Cypher查询语句:{cypher_query}")
        try:
            search_result, full_stream_text = graph_rag_fun(cypher_query,graph,prompt)
        except:
            print('rag fail')

   
    # 调用DeepSeek API  
    if full_stream_text!=None:
        content = full_stream_text
    else:
        response = client.chat.completions.create(  
            model=Model_name,  
            messages=st.session_state.messages,  
            # stream=True  
        )  
        content = ""
        if hasattr(response, 'choices') and response.choices:
            for choice in response.choices:
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    chunk_content = choice.message.content
                    # print(chunk_content, end='')  # 可选：打印内容
                    content += chunk_content  # 将内容累加到总内容中
        else:
            raise ValueError("Unexpected response structure")
    
    assistant_reply = content  
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})  
    st.chat_message("assistant").write(assistant_reply)
    # projects_data = [
    #     {
    #         "名称": "UCCA 陶美术馆",
    #         "图片": "https://www.archdaily.cn/cn/1023377/xiang-qian-nian-tao-du-xue-xi-wei-yan-wu-xin-zuo-ucca-tao-mei-zhu-guan/6721411eabb6a2129afa5851-ucca-clay-museum-kengo-kuma-and-associates-photo",  # 替换实际URL
    #         "层数": "2",
    #         "状态": "新建",
    #         "链接": "https://www.archdaily.cn/cn/1023377/xiang-qian-nian-tao-du-xue-xi-wei-yan-wu-xin-zuo-ucca-tao-mei-zhu-guan?ad_medium=office_landing&ad_name=article"
    #     },
    #     {
    #         "名称": "UCCB 陶美术馆",
    #         "图片": "https://snoopy.archdaily.com/images/archdaily/media/images/62b4/6eef/3e4b/311f/ee00/0010/medium_jpg/DSCF3367.jpg?1655992038&format=webp&width=320&height=220&crop=true",  # 替换实际URL
    #         "层数": "3",
    #         "状态": "新建",
    #         "链接": "https://www.archdaily.cn/cn/1023377/xiang-qian-nian-tao-du-xue-xi-wei-yan-wu-xin-zuo-ucca-tao-mei-zhu-guan?ad_medium=office_landing&ad_name=article"
    #     },
    #     {
    #         "名称": "UCCC 陶美术馆",
    #         "图片": "https://www.archdaily.cn/cn/887833/mian-wu-su-jian-zhu-she-ji-shi-wu-suo/5a6af357f197ccbe77000408-mian-wu-su-jian-zhu-she-ji-shi-wu-suo-zhao-pian",  # 替换实际URL
    #         "层数": "4",
    #         "状态": "新建",
    #         "链接": "https://www.archdaily.cn/cn/1023377/xiang-qian-nian-tao-du-xue-xi-wei-yan-wu-xin-zuo-ucca-tao-mei-zhu-guan?ad_medium=office_landing&ad_name=article"
    #     },
    #     {
    #         "名称": "UCCC 陶美术馆",
    #         "图片": "https://www.archdaily.cn/cn/887833/mian-wu-su-jian-zhu-she-ji-shi-wu-suo/5a6af357f197ccbe77000408-mian-wu-su-jian-zhu-she-ji-shi-wu-suo-zhao-pian",  # 替换实际URL
    #         "层数": "4",
    #         "状态": "新建",
    #         "链接": "https://www.archdaily.cn/cn/1023377/xiang-qian-nian-tao-du-xue-xi-wei-yan-wu-xin-zuo-ucca-tao-mei-zhu-guan?ad_medium=office_landing&ad_name=article"
    #     },
    #     # ... 其他项目数据（结构同上）
    # ]
    #  # ====== 新增图片展示功能 ======
    if search_result!=None and '图片' in search_result[0]['p']:
        search_result_list = []
        for sr in search_result:
            search_result_list.append(dict(sr['p']))
        with st.expander("📸 项目图片预览", expanded=True):
            # 创建响应式网格布局（每行3张图）
            cols = st.columns(1)
            for idx, project in enumerate(search_result_list):
                with cols[idx % 1]:
                    try:
                        # 显示图片（带标题和链接）
                        st.image(
                            project["图片"],
                            caption=f"{project['名称']} | {project['层数']}层",
                            width=200,
                            use_container_width='auto'
                        )
                        # 添加项目链接按钮
                        st.link_button("项目详情", project["链接"])
                    except Exception as e:
                        st.error(f"图片加载失败: {str(e)}")
        
        # ====== 保留JSON展示功能（可折叠） ======
        with st.expander("🔍 查看完整JSON数据"):
            formatted_json = json.dumps(search_result_list, ensure_ascii=False, indent=2)
            st.json(formatted_json)  # 保持JSON格式化展示[4](@ref)
    
