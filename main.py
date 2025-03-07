from flask import Flask, request, url_for,send_from_directory, session, redirect, send_file, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import re
import time
import requests
import zipfile
from io import BytesIO

# Load environment variables
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPE = 'user-library-read'

app = Flask(__name__)
app.secret_key = "elLtc+yL-%@Qv2-!cV"  # Replace with a secure key

# Folder to save downloaded images
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route("/")
def home():
    return render_template('home.html')

@app.route("/login")
def login():
    session.clear()
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

@app.route("/redirect")
def redirect_page():
    sp_oauth = create_spotify_oauth()
    session.clear()  # Clear the session to avoid conflicts
    code = request.args.get("code")
    if not code:
        return "Authorization failed: No code provided.", 400

    # Get the access token
    token_info = sp_oauth.get_access_token(code)
    if not token_info:
        return "Failed to retrieve access token.", 400

    # Get the user's Spotify ID
    sp = spotipy.Spotify(auth=token_info["access_token"])
    user_info = sp.current_user()
    user_id = user_info["id"]

    # Store the token info with a unique key
    session[f"{user_id}_token_info"] = token_info
    print(f"Debug: Token info stored for user {user_id}")
    return redirect(url_for("getImages", _external=True))

@app.route("/getImages")
def getImages():
    try:
        # Get the user's Spotify ID from the session
        user_id = get_user_id()
        if not user_id:
            raise Exception("User ID not found in session.")

        # Retrieve the token info using the user's ID
        token_info = get_token(user_id)
        print(f"Debug: Token info retrieved for user {user_id}")
    except Exception as e:
        print(f"Error: {e}")
        return redirect(url_for("login", _external=True))

    sp = spotipy.Spotify(auth=token_info["access_token"])
    images = {}
    limit = 50
    offset = 0
    while True:
        saved_albums = sp.current_user_saved_albums(limit=limit, offset=offset)
        if not saved_albums["items"]:
            break
        for item in saved_albums["items"]:
            album_info = item["album"]
            name = album_info["name"]
            url = album_info["images"][0]["url"]
            images[name] = url
        offset += limit

    # Save images to the download folder
    pattern = r'[<>:"/\\|?*]'
    for album, cover_image in images.items():
        response = requests.get(cover_image)
        if response.status_code == 200:
            clean_album_name = re.sub(pattern, "", album) + ".jpg"
            save_path = os.path.join(DOWNLOAD_FOLDER, clean_album_name)
            with open(save_path, 'wb') as f:
                f.write(response.content)
        else:
            print(f"Failed to download image for album: {album}")

    # List files in the download folder
    files = os.listdir(DOWNLOAD_FOLDER)
    return render_template('downloadPage.html', files=files)

@app.route('/download_all')
def download_all():
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zipf:
        for file in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, file)
            zipf.write(file_path, arcname=file)
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='downloaded_files.zip'
    )

def get_user_id():
    user_ids = []
    for key in session:
        if key.endswith("_token_info"):
            user_id = key.split("_")[0]
            user_ids.append(user_id)
    
    if len(user_ids) > 1:
        print(f"Warning: Multiple user IDs found in session: {user_ids}")
        # Clear all "_token_info" keys
        for key in list(session.keys()):
            if key.endswith("_token_info"):
                session.pop(key)
        return None
    print ("user id's: ",user_id)
    return user_ids[0] if user_ids else None

def get_token(user_id):
    # Retrieve the token info using the user's ID
    token_info = session.get(f"{user_id}_token_info")
    if not token_info:
        raise Exception(f"No token info found for user {user_id}.")

    # Check if the token is expired
    now = time.time()
    is_expired = token_info["expires_at"] - now < 60
    if is_expired:
        print(f"Debug: Token expired for user {user_id}. Refreshing token...")
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
        session[f"{user_id}_token_info"] = token_info  # Update the session with the new token

    return token_info

def create_spotify_oauth():
    redirect_uri = url_for("redirect_page", _external=True)
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=redirect_uri,
        scope=SCOPE
    )

if __name__ == "__main__":
    app.run()