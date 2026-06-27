import os
from PIL import Image

# Folder jahan images hain
folder_path = 'C:\\ABVE\\Stubble' 

for filename in os.listdir(folder_path):
    if filename.endswith(".webp"):
        # Image open karein
        img = Image.open(os.path.join(folder_path, filename)).convert("RGB")
        # .webp hata kar .jpg lagayein
        new_filename = os.path.splitext(filename)[0] + ".jpg"
        # Save as JPG
        img.save(new_filename, "JPEG")
        print(f"Converted: {filename} -> {new_filename}")