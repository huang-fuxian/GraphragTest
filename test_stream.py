# -*- coding: utf-8 -*-
import streamlit as st
from openai import OpenAI
from config import LLM_CONFIG
import json
# 设置特殊符号作为头像
USER_AVATAR = "👤"   # 用户头像符号
ASSISTANT_AVATAR = "🤖"  # 助手头像符号
# 注入CSS实现右对齐样式
st.markdown("""
<style>
    .user-message {
        text-align: right;
        margin: 10px 0;
        padding: 10px;
        background-color: #dbf3fa;
        border-radius: 10px;
        display: inline-block;
        max-width: 80%;
        float: right;
        clear: both;
    }
    .assistant-message {
        text-align: left;
        margin: 10px 0;
        padding: 10px;
        background-color: #f0f0f0;
        border-radius: 10px;
        display: inline-block;
        max-width: 80%;
        float: left;
        clear: both;
    }
</style>
""", unsafe_allow_html=True)

# 初始化API客户端
API_KEY = LLM_CONFIG["API_KEY"]
LLM_API_URL = LLM_CONFIG["API_URL"]
Model_name = LLM_CONFIG["Model"]
client = OpenAI(api_key=API_KEY, base_url=LLM_API_URL)

# 初始化消息列表（包含系统消息）
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

# 显示历史消息
for message in st.session_state.messages:
    if message["role"] != "system":  # 不显示系统消息
        if message["role"] == "user":
            with st.chat_message(message["role"], avatar=USER_AVATAR):
                st.markdown(f'<div class="user-message">{message["content"]}</div>', 
                        unsafe_allow_html=True)
        else:
            with st.chat_message(message["role"], avatar=ASSISTANT_AVATAR):
                st.markdown(f'<div class="assistant-message">{message["content"]}</div>', 
                        unsafe_allow_html=True)

# 用户输入处理
prompt = st.chat_input("输入问题...")
if prompt:
    # 添加用户消息到会话状态
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 立即显示用户消息（右对齐）
    st.markdown(f'<div class="user-message">{prompt}</div>', 
                unsafe_allow_html=True)
    
    # 调用API获取回复
    response = client.chat.completions.create(
        model=Model_name,
        messages=st.session_state.messages,
        stream=True
    )

    # 创建占位区域并实时显示回复
    placeholder = st.empty()
    full_response = ""
    for chunk in response:
        content = chunk.choices[0].delta.content or ""
        full_response += content
        placeholder.markdown(f'<div class="assistant-message">{full_response}▌</div>', 
                            unsafe_allow_html=True)
    
    # 最终更新回复内容（移除光标）
    placeholder.markdown(f'<div class="assistant-message">{full_response}</div>', 
                        unsafe_allow_html=True)
    
    # 添加助手消息到会话状态
    st.session_state.messages.append({"role": "assistant", "content": full_response})