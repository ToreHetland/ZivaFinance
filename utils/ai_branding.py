from google import genai
from PIL import Image
from io import BytesIO

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def generate_branded_icon(category_name: str):
    prompt = f"A professional 3D glassmorphism app icon for financial category '{category_name}'. Blue and silver theme, minimalist, high quality, white background."
    
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[prompt]
    )
    # The response contains the generated image bytes
    return response.generated_images[0].image_bytes