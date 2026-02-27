# import google.generativeai as genai

# # Replace with your actual Gemini API key
# genai.configure(api_key="AIzaSyAWA9Kqh2FRtBmxRZmNlZ7pcfasG5RJmR8")

# model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

# response = model.generate_content("Explain how AI works in a few words 500 words")

# print(response.text)
import logging
import google.generativeai as genai

# 1. Hard-code your API key here
API_KEY = "AIzaSyAWA9Kqh2FRtBmxRZmNlZ7pcfasG5RJmR8"

# 2. Configure the client
genai.configure(api_key=API_KEY)

def generate_summary(prompt: str) -> str:
    """
    Calls Gemini (Text-Bison) to generate a summary for the given prompt.
    """
    try:
        response = genai.generate_text(
            model="models/text-bison-001",
            prompt=prompt,
            temperature=0.2,          # control randomness
            max_output_tokens=512     # adjust as needed
        )
        return response.text
    except Exception as e:
        logging.error(f"[Gemini API] call failed: {e}", exc_info=True)
        return "Summary unavailable; check logs for details."
