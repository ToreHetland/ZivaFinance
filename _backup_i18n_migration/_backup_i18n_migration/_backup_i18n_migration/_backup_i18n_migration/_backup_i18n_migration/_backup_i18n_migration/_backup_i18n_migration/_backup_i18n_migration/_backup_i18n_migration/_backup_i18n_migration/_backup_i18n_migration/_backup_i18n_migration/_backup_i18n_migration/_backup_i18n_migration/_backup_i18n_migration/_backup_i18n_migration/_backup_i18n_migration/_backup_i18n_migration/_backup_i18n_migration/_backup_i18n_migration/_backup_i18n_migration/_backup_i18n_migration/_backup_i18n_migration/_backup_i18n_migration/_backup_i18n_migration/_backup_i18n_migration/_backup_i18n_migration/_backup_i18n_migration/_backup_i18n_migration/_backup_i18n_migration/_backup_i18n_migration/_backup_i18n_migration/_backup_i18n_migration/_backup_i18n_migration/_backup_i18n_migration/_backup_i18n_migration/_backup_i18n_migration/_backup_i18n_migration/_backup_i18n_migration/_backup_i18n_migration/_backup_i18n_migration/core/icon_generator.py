import os
import time
from io import BytesIO
from PIL import Image
import streamlit as st
from google import genai
from google.genai import types
from core.db_operations import load_data_db
from core.i18n import t

# Initialize the modern SDK client
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def generate_and_save_icons():
    """Loops through categories and generates custom 3D icons."""
    
    # 1. Load your 41 imported categories
    cat_df = load_data_db("categories")
    if cat_df.empty:
        st.warning("No categories found in database.")
        return

    # 2. Ensure the icon folder exists
    icon_dir = "assets/icons/categories"
    os.makedirs(icon_dir, exist_ok=True)

    st.info(f"🚀 Starting AI Icon Generation for {len(cat_df)} categories...")
    
    for idx, row in cat_df.iterrows():
        cat_name = row['name']
        safe_name = cat_name.replace(" ", "_").lower()
        file_path = f"{icon_dir}/{safe_name}.png"

        # Skip if the icon already exists to save quota
        if os.path.exists(file_path):
            continue

        st.write(f"🎨 Generating icon for: **{cat_name}**...")

        # 3. Craft a high-end Glassmorphism prompt
        prompt = (
            f"A professional 3D app icon for the financial category: '{cat_name}'. "
            "Style: Modern Glassmorphism with frosted glass effects. "
            "Colors: Deep blue and silver accents. "
            "Composition: Minimalist icon centered on a clean white background. "
            "Quality: 4K, high-fidelity, photorealistic textures."
        )

        try:
            # Call the Nano Banana (Gemini 2.5 Flash Image) model
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"]
                )
            )

            # 4. Process and Save the image
            for part in response.parts:
                if part.inline_data:
                    image_data = part.inline_data.data
                    img = Image.open(BytesIO(image_data))
                    
                    # Optional: Resize for performance
                    img = img.resize((512, 512))
                    img.save(file_path)
                    st.success(f"✅ Saved: {file_path}")
            
            # Small sleep to respect rate limits
            time.sleep(1)

        except Exception as e:
            st.error(f"❌ Failed to generate icon for {cat_name}: {e}")

    st.balloons()
    st.success("🎉 All category icons have been generated!")

if __name__ == "__main__":
    # You can trigger this manually from a button in your Admin Panel
    generate_and_save_icons()