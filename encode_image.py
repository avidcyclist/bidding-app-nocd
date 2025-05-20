import base64

# Path to your image file
image_path = r"c:\Users\Mitch\Desktop\jiubby.png"

# Open the file and encode it to Base64
with open(image_path, "rb") as image_file:
    base64_string = base64.b64encode(image_file.read()).decode('utf-8')
    print(base64_string)