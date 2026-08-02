from PIL import Image
import os

def extract_logo():
    img = Image.open('scratch/left_panel.png')
    # The logo is typically at the top center of the left panel.
    # Left panel is ~307px wide. 
    # Logo is roughly y: 40 to 120, x: 60 to 240
    logo_box = img.crop((80, 50, 220, 100))
    
    os.makedirs('assets/templates', exist_ok=True)
    logo_box.save('assets/templates/riot_logo.png')
    print("Logo template saved.")

if __name__ == "__main__":
    extract_logo()
