import requests
import tempfile
import os

def get_file_extension(filename):
    # Find the position of the last dot in the filename
    last_dot_index = filename.rfind('.')

    # If a dot is found and it's not the last character, return the extension
    if last_dot_index != -1 and last_dot_index < len(filename) - 1:
        return filename[last_dot_index + 1:]
    else:
        # If no valid extension is found, return an empty string or None
        return

def download_file_from_url(url):
    """Download a file from a URL and save it to a temporary file."""
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        # Create a temporary file
        extension = get_file_extension(url)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix="."+extension)
        with open(temp_file.name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return temp_file.name
    else:
        raise Exception(f"Failed to download file from URL. Status code: {response.status_code}")

def upload_file_to_gemini(url, client):
    temp_file_path = download_file_from_url(url)
    file = client.files.upload(file=temp_file_path)
    os.remove(temp_file_path)
    return file