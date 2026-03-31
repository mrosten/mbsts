import os
import sys
from dotenv import load_dotenv

def test_gemini():
    print("=== Gemini API Connection Test ===")
    
    # 1. Load .env
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded .env from {env_path}")
    else:
        print("Warning: .env file not found. Checking environment variables...")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env or environment.")
        return

    print(f"API Key found (length: {len(api_key)})")

    # 2. Try to import the library
    try:
        import google.generativeai as genai
    except ImportError:
        print("Error: google-generativeai is not installed.")
        print("Run: pip install -q -U google-generativeai")
        return

    # 3. Configure and Call
    try:
        genai.configure(api_key=api_key)
        
        print("Listing available models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"  - {m.name}")

        model_name = 'gemini-2.0-flash'
        print(f"\nSending test prompt to Gemini ('{model_name}')...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say hello from DARWIN and confirm you are connected.")
        
        print("\n--- Response ---")
        print(response.text)
        print("-----------------\n")
        print("Result: SUCCESS! Your Gemini connection is working perfectly.")
        
    except Exception as e:
        print(f"\nResult: FAILED!")
        print(f"Error details: {e}")
        if "API_KEY_INVALID" in str(e):
            print("Tip: Your API key appears to be invalid. Please check it in Google AI Studio.")

if __name__ == "__main__":
    test_gemini()
