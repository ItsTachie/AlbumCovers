from flask import Flask, request, url_for,session,redirect,send_from_directory,send_file,render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import re 
import time
import requests
import zipfile
from io import BytesIO


load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPE = 'playlist-read-private, playlist-read-collaborative, user-library-read'


app = Flask(__name__)

app.secret_key = "Oncsd23sdflo"
app.config["SESSION_COOKIE_NAME"] = "tachie's cookie"
TOKEN_INFO = "token_info"


DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)


@app.route("/")
def login():
    sp = create_spotify_oauth()
    auth_url = sp.get_authorize_url()
    return Flask.redirect(self=app, location=auth_url)

@app.route("/redirect")
def redirect():
    sp = create_spotify_oauth()
    session.clear()
    code = request.args.get("code")
    token_info = sp.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return Flask.redirect(self=app, location=url_for("getImages", _external=True))

@app.route("/getImages")
def getImages():
    try: 
        token_info = get_token()
    except:
        print("user not logged in")
        return Flask.redirect(self=app, location=url_for("login",_external=True))
    sp = spotipy.Spotify(auth = token_info["access_token"])
    images = dict()
    # Pagination variables
    limit = 50  # Number of items to fetch per request
    offset = 0  # Starting point for the next request
    has_more = True  # Flag to check if there are more items to fetch
    while has_more:
        # Fetch saved albums with the current offset and limit
        saved_albums = sp.current_user_saved_albums(limit=limit, offset=offset)
        
        # Check if there are any items in the response
        if not saved_albums["items"]:
            has_more = False
            break
        
        # Process each album in the current batch
        for item in saved_albums["items"]:
            album_info = item["album"]
            name = album_info["name"]
            url = album_info["images"][0]["url"]
            images[name] = url
        
        # Update the offset for the next request
        offset += limit



    # Regular expression pattern to clean filenames
    pattern = r'[<>:"/\\|?*]'

    for album, cover_image in images.items():
        response = requests.get(cover_image)
        if response.status_code == 200:
            # Clean the album name for use as a filename
            clean_album_name = re.sub(pattern, "", album) + ".jpg"
            save_path = os.path.join(DOWNLOAD_FOLDER, clean_album_name)
            # Save the image
            #replace directory with the appropriate folder to save the file to 
            with open(save_path, 'wb') as f:
                f.write(response.content)
        else:
            print(f"Failed to download image for album: {album}")
    # Print the number of albums fetched
    files = os.listdir(DOWNLOAD_FOLDER)
    return render_template('downloadPage.html', files=files)


    
    
    #return sp.current_user_saved_albums(limit=50, offset=0)["items"][0]

@app.route('/download_all')
def download_all():
    # Create a ZIP file in memory
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zipf:
        for file in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, file)
            zipf.write(file_path, arcname=file)

    # Move the cursor to the beginning of the file
    memory_file.seek(0)

    # Return the ZIP file as a downloadable response
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='downloaded_files.zip'
    )


def get_token():
    token_info = session.get(TOKEN_INFO)
    if not token_info:
        raise "exception"
    now = time.time()
    is_expired = token_info["expires_at"] - now < 60
    if is_expired:
        sp = create_spotify_oauth()
        token_info = sp.refresh_access_token(token_info["refresh_token"])
    return token_info



def create_spotify_oauth():
    redirect_uri = url_for("redirect", _external=True)
    print("Debug: Redirect URI:", redirect_uri)
    return SpotifyOAuth(client_id=CLIENT_ID,
                        client_secret=CLIENT_SECRET,
                        redirect_uri=url_for("redirect", _external=True),
                        scope=SCOPE)


if __name__ == "__main__":
    app.run()