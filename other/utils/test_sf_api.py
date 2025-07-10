from openai import OpenAI
from langchain.prompts import ChatPromptTemplate

# API密钥
API_KEY = 'sk-icchogndqscnbeniasywjjmyukqsyxfnewjiiuioqglwejmc'

# 自定义硅基流动大模型类
class CustomLLM_Siliconflow:
    def __call__(self, prompt: str) -> str:
        # 初始化OpenAI客户端（base_url是硅基流动网站的地址）
        client = OpenAI(api_key=API_KEY, base_url="https://api.siliconflow.cn/v1")
        
        # 发送请求到模型
        response = client.chat.completions.create(
            model='THUDM/glm-4-9b-chat',
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

        return content  # 返回最终的响应内容

# 创建自定义LLM实例
llm = CustomLLM_Siliconflow()
    
# 示例查询：将大象装进冰箱分几步？
print(llm("把大象装进冰箱分几步？")) 