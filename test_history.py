import streamlit as st

# 初始化会话状态变量
if "editing_index" not in st.session_state:
    st.session_state.editing_index = None  # 当前编辑的对话索引
if "deleted_indices" not in st.session_state:
    st.session_state.deleted_indices = set()  # 标记删除的对话索引
if "history_conversations" not in st.session_state:
    st.session_state.history_conversations = []  # 初始化为空列表

st.subheader("历史对话")

# 数据结构转换（兼容旧版本）
if st.session_state.history_conversations and isinstance(st.session_state.history_conversations[0], list):
    # 将旧格式(纯消息列表)转换为新格式(带标题的字典)[7](@ref)
    st.session_state.history_conversations = [
        {"title": f"对话 {i+1}", "messages": messages, "deleted": False}
        for i, messages in enumerate(st.session_state.history_conversations)
    ]

# 显示历史对话列表
if st.session_state.history_conversations:
    conv_num = len(st.session_state.history_conversations)
    
    for idx in range(conv_num-1, -1, -1):
        conv = st.session_state.history_conversations[idx]
        
        # 跳过已删除的对话
        if conv.get("deleted"):
            continue
            
        # 创建列布局：标题+操作按钮
        cols = st.columns([0.7, 0.15, 0.15])
        
        with cols[0]:
            # 编辑状态显示输入框
            if st.session_state.editing_index == idx:
                new_title = st.text_input(
                    "新标题", 
                    value=conv["title"],
                    key=f"edit_{idx}",
                    label_visibility="collapsed"
                )
            # 正常状态显示可点击标题
            else:
                if st.button(
                    conv["title"], 
                    key=f"load_{idx}",
                    use_container_width=True
                ):
                    st.session_state.messages = conv["messages"]
        
        with cols[1]:
            # 重命名按钮
            if st.session_state.editing_index == idx:
                if st.button("✅", key=f"save_{idx}", help="保存标题"):
                    conv["title"] = new_title
                    st.session_state.editing_index = None
                    st.rerun()
            else:
                if st.button("✏️", key=f"rename_{idx}", help="重命名对话"):
                    st.session_state.editing_index = idx
                    st.rerun()
        
        with cols[2]:
            # 删除按钮
            if st.button("🗑️", key=f"delete_{idx}", help="删除对话"):
                # 标记为删除（逻辑删除）[7](@ref)
                conv["deleted"] = True
                st.session_state.deleted_indices.add(idx)
                st.rerun()
    
    # 永久删除按钮
    if st.session_state.deleted_indices:
        if st.button("永久删除已标记对话", type="primary"):
            # 物理删除已标记的对话[8](@ref)
            st.session_state.history_conversations = [
                conv for idx, conv in enumerate(st.session_state.history_conversations)
                if not conv.get("deleted")
            ]
            st.session_state.deleted_indices = set()
            st.rerun()
else:
    st.write("暂无历史对话")