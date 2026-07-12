import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

image_path = os.path.join(os.getcwd(), "test.jpg")

print("Exists:", os.path.exists(image_path))
print("Path:", image_path)

result = cloudinary.uploader.upload(
    image_path,
    folder="svpg-test"
)

print(result["secure_url"])