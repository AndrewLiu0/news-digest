from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

# Central model instances - Using GPT-4o-mini for both tasks for speed and cost-efficiency
# Both models are set to gpt-4o-mini
reasoning_model = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_retries=5)
fast_model = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_retries=5)

# Default model for backward compatibility
model = reasoning_model
