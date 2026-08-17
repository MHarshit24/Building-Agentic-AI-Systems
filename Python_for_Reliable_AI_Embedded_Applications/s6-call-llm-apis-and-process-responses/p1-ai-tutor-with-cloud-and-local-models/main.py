import os
from dotenv import load_dotenv
from google import genai
import requests

# ============================================================
# Load Environment Variables
# ============================================================

load_dotenv(r"C:\Users\harsh\NIIT\Building_Agentic_AI_Systems\.env")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

base_url = os.getenv("GEMINI_ENDPOINT")
if not base_url:
    raise ValueError("GEMINI_ENDPOINT not found in environment variables")

gemini_model = os.getenv("GEMINI_MODEL")
if not gemini_model:    
    raise ValueError("GEMINI_MODEL not found in environment variables")

client = genai.Client(api_key=api_key)

# ============================================================
# Cloud Model (Gemini) - Factual Explanation
# ============================================================

def get_cloud_explanation_streaming(user_query: str) -> str:
    try:
        response = client.models.generate_content(
            model=gemini_model,
            contents=f"Provide a clear and accurate technical explanation of: {user_query}"
        )
        return response.text
    
    except Exception as e:
        return f"[ERROR: Cloud Model Failed] {str(e)}"
    

# ============================================================
# Local Model (Ollama) - Creative Personalization
# ============================================================  

def get_local_personalization(gemini_explanation: str) -> str:
    try:
        url = "http://localhost:11434/api/generate"
        
        prompt = (
                f"Rewrite this technical explanation in a highly engaging, fun, "
                f"and personally relatable story or analogy for a beginner student "
                f"exploring Agentic AI. Be creative and do not exceed 4 sentences.\n\n"
                f"The explanation is:\n\n---\n{gemini_explanation}"
            )
        
        payload = {
                "model": "phi3:mini",
                "prompt": prompt,
                "stream": False
            }
        
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json()["response"]
        else:
            return f"[ERROR: Local Model Failed] Status Code: {response.status_code}"
        
    except KeyboardInterrupt:
        print("\n\nExecution interrupted by user. Goodbye!")
        exit(0)
            
    except Exception as e:
        return f"[ERROR: Could not complete Model Call] {str(e)}"

# ============================================================
# Main Tutor Agent Loop
# ============================================================

def main():
    print("=" * 60)
    print("Study Buddy - A Personalized AI Tutor with LLM Models")
    print("=" * 60)
    print("Step 1 (Cloud): Factual Explanation.")
    print("Step 2 (Local): Creative Personalization.")
    print()

    while True:
        user_input = input(
            "\nEnter an Agentic AI concept (e.g., RAG, LLM, Planning) or 'quit': "
        )

        if user_input.lower() == "quit" or user_input.lower() == "exit":
            print("\nGoodbye! Keep learning with AI.")
            break

        print("\n--- [1] CLOUD MODEL (Gemini) - Factual Explanation ---\n")
        cloud_response = get_cloud_explanation_streaming(user_input)
        print(cloud_response)

        print("\n--- [2] LOCAL MODEL (Llama phi3 mini) - Private Personalization ---\n")
        local_response = get_local_personalization(cloud_response)
        print(local_response)


if __name__ == "__main__":
    main()
