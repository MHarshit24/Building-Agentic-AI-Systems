from dotenv import load_dotenv
import os
from google import genai

load_dotenv(r"C:\Users\harsh\NIIT\Building_Agentic_AI_Systems\.env")

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

for model in client.models.list():
    print(model.name)