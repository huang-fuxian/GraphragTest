# -*- coding: utf-8 -*-
import json
import streamlit as st  
from openai import OpenAI   
from utils import context_aware_kg_qa,extract_cypher_from_llm_output,configure_neo4j,graph_rag_fun,simple_extract_cypher,get_context_aware_response_stream
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
        conv_num = len(st.session_state.history_conversations)
        for idx in range(conv_num,-1,-1):
            if st.button(f"对话 {idx + 1}", key=f"load_conv_{idx}"):  
                st.session_state.messages = st.session_state.history_conversations[idx]  
        # for idx, conv in enumerate(st.session_state.history_conversations):  
        #     if st.button(f"对话 {idx + 1}", key=f"load_conv_{idx}"):  
        #         st.session_state.messages = conv  
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

    with open("log.txt", 'a+', encoding='utf-8') as f:
        f.write(f"-*"*50+ "\n")
        f.write(f"question:{prompt} \n")
    graph = configure_neo4j()
    with st.spinner("🤔 正在分析您的问题..."):
        response_query = context_aware_kg_qa(prompt)
        cypher_query = simple_extract_cypher(response_query)
        content = ""
        full_stream_text = ""
        result = None
      
        if cypher_query: 
            try:
                result = graph.run(cypher_query).data()
                if result and len(result)>0:
                    st.markdown("**🔍 查询结果：**")
                    with st.expander(f"🔍 查看查询结果 ({len(result)} 条)", expanded=False):
                        # 优化展示，保证每条完整，内容过长时减少条数                    
                        max_display = 10
                        max_chars = 4000
                        display_list = []
                        total_chars = 0
                        for item in result[:max_display]:
                            item_str = json.dumps(item, ensure_ascii=False)
                            if total_chars + len(item_str) > max_chars:
                                break
                            display_list.append(item)
                            total_chars += len(item_str)
                        if not display_list and result:
                            # 如果第一条就超长，至少展示一条
                            display_list = [result[0]]
                        st.json(display_list)
                    with st.expander("📝 查看Cypher查询语句", expanded=False):
                        st.code(cypher_query, language="cypher")
                    summary_prompt = f"用户问题：{prompt}\n查询结果：{result[:8]}\n请用中文总结这些结果。"
                    try:
                        st.markdown("**🤖 AI智能总结：**")
                        stream_placeholder = st.empty()
                        full_stream_text = ""
                        for chunk in get_context_aware_response_stream(
                            question=summary_prompt,
                            history=[],
                            client=client,
                            model_name=Model_name,
                            max_tokens=2000
                        ):
                            full_stream_text += chunk
                            stream_placeholder.markdown(full_stream_text)
                        if full_stream_text and len(full_stream_text.strip()) > 5:
                            content = full_stream_text
                            st.success("✅ AI总结生成成功")
                            st.session_state.messages.append({"role": "assistant", "content": "🤖 AI智能总结：" + full_stream_text})
                            # st.session_state.qa_system.add_to_history("assistant", "🤖 AI智能总结：" + full_stream_text)
                        else:
                            st.warning("AI总结内容为空")
                    except Exception as e:
                        st.warning(f"AI总结失败: {str(e)}")                    
                else:
                    st.warning("未查到相关内容，请尝试调整您的问题或关键词。")
                    st.session_state.messages.append({"role": "assistant", "content": "未查到相关内容，请尝试调整您的问题或关键词。"})
                    # st.session_state.qa_system.add_to_history("assistant", "未查到相关内容，请尝试调整您的问题或关键词。")
            except Exception as e:
                st.error(f"❌ Cypher 执行出错: {str(e)}")
        else:
            st.warning("未提取到Cypher查询，显示原始AI响应")
        if full_stream_text=="":                
            st.markdown("**🤖 AI回答：**")
            response = client.chat.completions.create(  
                model=Model_name,  
                messages=[{"role": "user", "content": prompt}],  
                max_tokens=1000,  # 适中的长度
                temperature=0.3,
                stream=True  
            )  

            placeholder = st.empty()  # 创建占位区域
            # placeholder.markdown("Cypher查询语句：")
            full_response = ""
            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                full_response += content
                placeholder.markdown(full_response) 
            content =full_response

            # st.markdown(content)
        # if full_stream_text=="":
            
    with open("log.txt", 'a+', encoding='utf-8') as f:
        f.write(f"response:{content} \n")
    assistant_reply = content  
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})  
    # st.chat_message("assistant").write(assistant_reply)
   
    # if search_result!=None and 'p' in search_result[0] and '图片' in search_result[0]['p']:
    #     search_result_list = []
    #     for sr in search_result:
    #         search_result_list.append(dict(sr['p']))
    #     with st.expander("📸 项目图片预览", expanded=True):
    #         # 创建响应式网格布局（每行3张图）
    #         cols = st.columns(1)
    #         for idx, project in enumerate(search_result_list):
    #             with cols[idx % 1]:
    #                 try:
    #                     # 显示图片（带标题和链接）
    #                     st.image(
    #                         project["图片"],
    #                         caption=f"{project['名称']} | {project['层数']}层",
    #                         width=200,
    #                         use_container_width='auto'
    #                     )
    #                     # 添加项目链接按钮
    #                     st.link_button("项目详情", project["链接"])
    #                 except Exception as e:
    #                     st.error(f"图片加载失败: {str(e)}")
        
    #     # ====== 保留JSON展示功能（可折叠） ======
    #     with st.expander("🔍 查看完整JSON数据"):
    #         formatted_json = json.dumps(search_result_list, ensure_ascii=False, indent=2)
    #         st.json(formatted_json)  # 保持JSON格式化展示[4](@ref)
    
