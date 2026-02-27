from fastapi import FastAPI
from pydantic import BaseModel
from groq import Groq
import os
from datetime import datetime

# Configure API key
API_KEY = os.getenv("GROQ_API_KEY")


# Initialize Groq client globally
client = Groq(api_key=API_KEY)
print("API KEY FOUND:", API_KEY is not None)

# Model configuration
MODEL_NAME = "llama-3.1-8b-instant"

# System prompt
system_prompt = """
You are FarmMatrix, an AI assistant for Indian farmers.
Provide practical farming advice on these topics:
- Crop selection and sowing
- Soil health and fertilizers
- Pest and disease control
- Irrigation and water management
- Weather-based farming tips
- Government schemes and subsidies
Response guidelines:
- Give direct, practical answers with action plans
- Use simple language that farmers can understand
- Provide detailed information in 2-4 paragraphs
- Don't introduce yourself every time - get straight to the point
- Only reference previous conversation for follow-up questions
CRITICAL LANGUAGE RULE:
- If the question is asked in Hindi, respond in Hindi
- If the question is asked in English, respond in English
- Match the language of the user's question exactly
- Use simple, farmer-friendly vocabulary in the chosen language
"""

# Helper functions
def detect_language(text):
    hindi_chars = sum(1 for char in text if '\u0900' <= char <= '\u097F')
    english_chars = sum(1 for char in text if char.isalpha() and char.isascii())
    total_chars = hindi_chars + english_chars
    if total_chars == 0:
        return "english"
    hindi_ratio = hindi_chars / total_chars
    return "hindi" if hindi_ratio > 0.3 else "english"

def get_language_specific_prompts(language):
    if language == "hindi":
        return {
            'question_label_simple': 'सवाल:',
            'direct_instruction': 'कृपया इस खेती के सवाल का सीधा और व्यावहारिक जवाब दें।'
        }
    else:
        return {
            'question_label_simple': 'Question:',
            'direct_instruction': 'Please provide a direct and practical answer to this farming question.'
        }

# Pydantic models
class GenerateRequest(BaseModel):
    question: str
    username: str

class GenerateResponse(BaseModel):
    username: str
    answer: str
    time: str

# FastAPI app
app = FastAPI()

# API Endpoint
@app.post("/generate")
def generate(request: GenerateRequest):
    question = request.question
    username = request.username

    question_language = detect_language(question)
    language_prompts = get_language_specific_prompts(question_language)

    user_message = f"{language_prompts['question_label_simple']} {question}\n\n{language_prompts['direct_instruction']}"

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=500,
            top_p=0.8,
        )
        answer = response.choices[0].message.content.strip()

    except Exception as e:
        print(f"ERROR TYPE: {type(e).__name__}")  # ← shows what kind of error
        print(f"ERROR DETAIL: {e}")               # ← shows full error message
        error_msg = (
            f"माफ करिए, कुछ परेशानी हो रही है: {str(e)}"
            if question_language == "hindi"
            else f"Sorry, an error occurred: {str(e)}"
        )
        return GenerateResponse(
            username=username,
            answer=error_msg,       # ← removed the invalid `e=e` argument
            time=datetime.now().isoformat()
        )

    return GenerateResponse(
        username=username,
        answer=answer,
        time=datetime.now().isoformat()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860) 