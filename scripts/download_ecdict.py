import urllib.request
import zipfile
import io
import os

URL = "https://github.com/skywind3000/ECDICT/releases/download/1.0.4/ecdict.csv.zip"
OUTPUT_DIR = r"d:\lian\praPro\h-videoE"

print("Downloading ECDICT...")
response = urllib.request.urlopen(URL, timeout=120)
zip_data = response.read()
print(f"Downloaded {len(zip_data)} bytes")

print("Extracting...")
with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
    zf.extractall(OUTPUT_DIR)

csv_path = os.path.join(OUTPUT_DIR, "ecdict.csv")
if os.path.exists(csv_path):
    size = os.path.getsize(csv_path) / (1024 * 1024)
    print(f"Extracted: {csv_path} ({size:.2f} MB)")
else:
    print("Extraction failed")