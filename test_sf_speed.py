# -*- coding: utf-8 -*-
import time
from openai import OpenAI
from config import LLM_CONFIG
import numpy  as np

def llm_query(client, prompt):

    messages = []
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
            model=Model_name,
            messages=messages,
            stream=True
        )
    t1=time.time()
    full_response = ""  # 存储完整响应
    print("AI: ", end="", flush=True)  # 准备实时输出

    try:
        # 逐块处理流式响应
        for chunk in response:
            if chunk.choices:  # 检查有效数据块[5,7](@ref)
                delta = chunk.choices[0].delta
                
                # 提取内容增量
                if hasattr(delta, 'content') and delta.content: 
                    content = delta.content
                    print(content, end="", flush=True)  # 实时输出内容
                    full_response += content  # 累积完整响应
                    
            # 可选：处理函数调用（若有）
            if hasattr(chunk.choices[0].delta, 'function_call'):
                function_call = chunk.choices[0].delta.function_call
                # 此处添加函数调用处理逻辑[1](@ref)
        
        print("\n")  # 流式结束后换行
    except Exception as e:
        print(f"\n[流式输出异常: {str(e)}]")

    t2 = time.time()
    return full_response, t2-t1

API_KEY = LLM_CONFIG["API_KEY"]
LLM_API_URL = LLM_CONFIG["API_URL"]
Model_name = LLM_CONFIG["Model"]
client = OpenAI(api_key=API_KEY, base_url=LLM_API_URL)
prompt = "What is WAIC? where it will be held in 2025?"
prompt_list = ["What is WAIC? where it will be held in 2025?","How to make cake?","How to learn AI?","what is 1+2+3?","What is the tallest building in china?","Why the sun can be with moon at the same time on the sky?"]
all_time_list = []
for prompt in prompt_list:
    time_list = []
    response_list = []
    run_times = 10
    for _ in range(run_times):
        response, cost_time = llm_query(client,prompt)
        time_list.append(cost_time)
        response_list.append(response)
    print_str = f"Run {run_times} for {Model_name}, mean time:{np.mean(time_list)}, max:{np.max(time_list)}, min:{np.min(time_list)}"
    all_time_list.append([np.mean(time_list),np.max(time_list),np.min(time_list)])
    print(print_str)
    with open("log.txt", 'a+', encoding='utf-8') as f:
        f.write(f"-*"*50)
        f.write(f"prompt:{prompt}")
        f.write(f"response:{print_str} \n")
        for i in range(run_times):
            f.write(f"run {i} time:{time_list[i]}")
            f.write(f"run {i} response:{response_list[i]}")
print(all_time_list)