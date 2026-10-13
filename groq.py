import requests
import json

def get_groq_legal_response(user_query):
    # 1. API Configuration
    url = "https://api.groq.com/openai/v1/chat/completions"
    api_key = "Replace with your actual key"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 2. Payload (Framework Step: Prediction ASD/Legal)
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system", 
                "content": "You are VakilAI, an expert in the Indian Judicial System and BNS."
            },
            {
                "role": "user", 
                "content": user_query
            }
        ],
        "temperature": 0.5
    }

    try:
        # 3. Model Execution
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status() # Check for errors
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        return f"Error: {str(e)}"

# --- Execution ---
if __name__ == "__main__":
    query = "Explain the transition from IPC to BNS for a law student."
    print("VakilAI is thinking...")
    print(get_groq_legal_response(query))
