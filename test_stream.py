# -*- coding: utf-8 -*-
import streamlit as st
from openai import OpenAI
from config import LLM_CONFIG
import json
import copy  # 用于深拷贝消息列表
from datetime import datetime  # 用于生成时间戳

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
    
    /* 新增：历史对话项样式 */
    .history-item {
        padding: 8px;
        margin: 4px 0;
        border-radius: 5px;
        cursor: pointer;
        transition: background-color 0.2s;
    }
    .history-item:hover {
        background-color: #f0f0f0;
    }
</style>
""", unsafe_allow_html=True)

# 初始化API客户端
API_KEY = LLM_CONFIG["API_KEY"]
LLM_API_URL = LLM_CONFIG["API_URL"]
Model_name = LLM_CONFIG["Model"]

# 初始化会话状态
def initialize_session_state():
    if "editing_index" not in st.session_state:
        st.session_state.editing_index = None
    if "deleted_indices" not in st.session_state:
        st.session_state.deleted_indices = set()
    if "history_conversations" not in st.session_state:
        st.session_state.history_conversations = []
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
    if "current_conversation_id" not in st.session_state:
        st.session_state.current_conversation_id = None

initialize_session_state()

# 侧边栏 - 历史对话管理
with st.sidebar:  
    st.subheader("历史对话")
    
    st.markdown("""
        <style>
            .hidden-button {
                display: none !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # 添加"新建对话"按钮
    if st.button("➕ 开启新对话", use_container_width=True):
        # 保存当前对话
        if len(st.session_state.messages) > 1:  # 确保不只是系统消息
            new_title = f"对话 {len(st.session_state.history_conversations) + 1}"
            new_conversation = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "title": new_title,
                "messages": copy.deepcopy(st.session_state.messages),
                "deleted": False,
                "timestamp": datetime.now().isoformat()
            }
            st.session_state.history_conversations.append(new_conversation)
        
        # 重置当前对话
        st.session_state.messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "assistant", "content": "欢迎开始新对话！有什么我可以帮您的？"}
        ]
        st.session_state.current_conversation_id = None
        st.rerun()
    
    # 数据结构转换（兼容旧版本）
    if st.session_state.history_conversations and isinstance(st.session_state.history_conversations[0], list):
        st.session_state.history_conversations = [
            {
                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "title": f"对话 {i+1}", 
                "messages": messages, 
                "deleted": False,
                "timestamp": datetime.now().isoformat()
            }
            for i, messages in enumerate(st.session_state.history_conversations)
        ]

    # 显示历史对话列表
    if st.session_state.history_conversations:
        # 按时间倒序排序（最新对话在最上面）
        sorted_conversations = sorted(
            st.session_state.history_conversations,
            key=lambda x: x["timestamp"],
            reverse=True
        )
        
        for conv in sorted_conversations:
            if conv.get("deleted"):
                continue
                
            # 创建列布局：标题+操作按钮
            cols = st.columns([0.7, 0.15, 0.15])
            
            with cols[0]:
                # 编辑状态显示输入框
                if st.session_state.editing_index == conv["id"]:
                    new_title = st.text_input(
                        "新标题", 
                        value=conv["title"],
                        key=f"edit_{conv['id']}",
                        label_visibility="collapsed"
                    )
                # 正常状态显示可点击标题
                else:
                    # 修改：使用自定义CSS类隐藏按钮
                    st.button(
                        conv["title"], 
                        key=f"load_{conv['id']}",
                        use_container_width=True,
                        # 新增className参数应用隐藏样式
                        # className="hidden-button"  
                    )
                    # 保持原有的点击事件处理
                    if st.session_state.get(f"load_{conv['id']}"):
                        st.session_state.messages = copy.deepcopy(conv["messages"])
                        st.session_state.current_conversation_id = conv["id"]
                        st.rerun()
            
            with cols[1]:
                # 重命名按钮
                if st.session_state.editing_index == conv["id"]:
                    if st.button("✅", key=f"save_{conv['id']}", help="保存标题"):
                        conv["title"] = new_title
                        st.session_state.editing_index = None
                        st.rerun()
                else:
                    if st.button("✏️", key=f"rename_{conv['id']}", help="重命名对话"):
                        st.session_state.editing_index = conv["id"]
                        st.rerun()
            
            with cols[2]:
                # 删除按钮
                if st.button("🗑️", key=f"delete_{conv['id']}", help="删除对话"):
                    conv["deleted"] = True
                    st.session_state.deleted_indices.add(conv["id"])
                    st.rerun()
        
        # 永久删除按钮
        if st.session_state.deleted_indices:
            if st.button("永久删除已标记对话", type="primary"):
                st.session_state.history_conversations = [
                    conv for conv in st.session_state.history_conversations
                    if not conv.get("deleted")
                ]
                st.session_state.deleted_indices = set()
                st.rerun()
    else:
        st.write("暂无历史对话")

client = OpenAI(api_key=API_KEY, base_url=LLM_API_URL)

# 显示当前对话的聊天消息
for message in st.session_state.messages:
    if message["role"] == "system":  # 不显示系统消息
        continue
        
    if message["role"] == "user":
        with st.chat_message(message["role"]):
            st.markdown(f'<div class="user-message">{message["content"]}</div>', 
                    unsafe_allow_html=True)
    else:
        with st.chat_message(message["role"]):
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
    
    # 自动保存当前对话到历史记录（如果尚未保存）
    if st.session_state.current_conversation_id is None and len(st.session_state.messages) > 2:
        new_title = f"对话 {len(st.session_state.history_conversations) + 1}"
        new_conversation = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "title": new_title,
            "messages": copy.deepcopy(st.session_state.messages),
            "deleted": False,
            "timestamp": datetime.now().isoformat()
        }
        st.session_state.history_conversations.append(new_conversation)
        st.session_state.current_conversation_id = new_conversation["id"]