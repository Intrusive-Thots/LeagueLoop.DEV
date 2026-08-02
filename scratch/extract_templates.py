from PIL import Image
import os

def extract():
    img = Image.open('scratch/left_panel.png')
    
    # Based on the earlier pixel calculation:
    # username_x = win_x + 137, username_y = win_y + 290
    # The label "USERNAME" should be above it, so around y = 260.
    # Let's crop a box that includes the text "USERNAME"
    # Left panel width is 307px (1536 * 0.2)
    # The fields are centered horizontally.
    
    # We will crop the whole input box for Username
    username_box = img.crop((40, 260, 260, 320))
    
    # Password box is ~56px below
    password_box = img.crop((40, 320, 260, 380))
    
    os.makedirs('assets/templates', exist_ok=True)
    username_box.save('assets/templates/username_field.png')
    password_box.save('assets/templates/password_field.png')
    print("Templates saved.")

if __name__ == "__main__":
    extract()
