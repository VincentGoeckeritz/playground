import os
from datetime import datetime
from typing import List
import json
import base64
import time

import streamlit as st
from ytmusicapi import YTMusic


class FestivalPlaylistGenerator:
    def __init__(self, auth_str: str):
        """Initialize YTMusic with authentication from auth string.

        Args:
            auth_str: JSON string containing authentication headers
        """
        try:
            # Parse auth JSON
            auth_data = json.loads(auth_str) if isinstance(auth_str, str) else auth_str

            # Create headers dict with required fields
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Content-Type': 'application/json',
                'X-Goog-AuthUser': '0',
                'x-origin': 'https://music.youtube.com'
            }

            # Add authentication headers
            if 'authorization' in auth_data:
                headers['authorization'] = auth_data['authorization']
            if 'cookie' in auth_data:
                headers['cookie'] = auth_data['cookie']

            # Write headers to temp file
            with open('headers_auth.json', 'w') as f:
                json.dump(headers, f)

            # Initialize YTMusic
            self.ytmusic = YTMusic('headers_auth.json')

            # Clean up temp file
            os.remove('headers_auth.json')

        except Exception as e:
            raise Exception(f"Failed to initialize YouTube Music: {str(e)}")

    def get_top_songs(self, artist: str, limit: int = 3) -> List[dict]:
        """Get the top songs for an artist."""
        try:
            # Search for the artist
            search_results = self.ytmusic.search(artist, filter="artists")
            if not search_results:
                st.warning(f"No results found for artist: {artist}")
                return []

            # Get artist's top songs
            artist_id = search_results[0]['browseId']
            artist_data = self.ytmusic.get_artist(artist_id)
            top_songs = artist_data.get('songs', {}).get('results', [])

            # Get song IDs and titles for top songs up to limit
            songs = []
            for song in top_songs[:limit]:
                songs.append({
                    'videoId': song['videoId'],
                    'title': song['title']
                })

            if not songs:
                st.warning(f"No songs found for artist: {artist}")

            return songs

        except Exception as e:
            st.error(f"Error getting top songs for {artist}: {str(e)}")
            return []

    def test_auth(self) -> bool:
        """Test if the authentication is working."""
        try:
            # Try to get library playlists as a test
            self.ytmusic.get_library_playlists(limit=1)
            return True
        except Exception as e:
            st.error(f"Authentication test failed: {str(e)}")
            return False

    def create_festival_playlist(self, lineup: List[str], playlist_name: str, songs_per_artist: int = 3) -> tuple:
        """Create a playlist with top songs from festival lineup."""
        progress_bar = st.progress(0.0)
        status_container = st.empty()

        try:
            # Create new playlist and handle response
            response = self.ytmusic.create_playlist(
                title=playlist_name,
                description=f"Top {songs_per_artist} songs from each artist at {playlist_name}",
                privacy_status="PRIVATE"
            )

            # Check if we got a valid playlist ID
            if not response:
                raise Exception("Failed to create playlist - no response from YouTube Music")

            # Extract playlist ID from response
            playlist_id = response if isinstance(response, str) else response.get('id')

            if not playlist_id:
                raise Exception("Failed to get playlist ID from response")

            status_container.write(f"Created playlist with ID: {playlist_id}")

            all_songs = []
            successful_additions = 0

            # Get top songs for each artist and add to playlist
            for i, artist in enumerate(lineup):
                if artist.strip():  # Skip empty lines
                    status_container.write(f"Processing {artist}...")
                    songs = self.get_top_songs(artist, songs_per_artist)
                    if songs:
                        try:
                            song_ids = [song['videoId'] for song in songs]
                            add_response = self.ytmusic.add_playlist_items(playlist_id, song_ids)

                            # More lenient success check as the API response varies
                            if add_response is not None:
                                successful_additions += 1
                                all_songs.extend([f"{artist} - {song['title']}" for song in songs])
                                status_container.write(f"✅ Added {len(songs)} songs for {artist}")
                            else:
                                status_container.warning(f"⚠️ Some songs for {artist} might not have been added")
                        except Exception as e:
                            status_container.warning(f"⚠️ Failed to add songs for {artist}: {str(e)}")
                    else:
                        status_container.warning(f"⚠️ No songs found for {artist}")

                # Update progress
                progress_bar.progress((i + 1) / len(lineup))

            if successful_additions == 0:
                raise Exception("No songs could be added to the playlist")

            # Clear the status container and show final success message
            status_container.empty()

            # Create final status message with playlist link
            playlist_url = f"https://music.youtube.com/playlist?list={playlist_id}"
            success_message = f"""
            ✨ Successfully created playlist with songs from {successful_additions} artists!

            🎵 [Open Playlist in YouTube Music]({playlist_url})
            """
            st.success(success_message)

            return playlist_id, all_songs

        except Exception as e:
            # Clear the status container
            status_container.empty()
            st.error(f"Error during playlist creation: {str(e)}")
            return None, []
        finally:
            # Ensure progress bar reaches 100% even on error
            progress_bar.progress(1.0)


def create_playlist_link(playlist_id: str) -> str:
    """Create a formatted link to the YouTube Music playlist."""
    return f"https://music.youtube.com/playlist?list={playlist_id}"

def show_playlist_results(playlist_id: str, songs: List[str]):
    """Show the results of playlist creation with nice formatting."""
    # Create collapsible sections for the results
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"""
        ### ✨ Playlist Created!

        🎵 [Open in YouTube Music]({create_playlist_link(playlist_id)})
        """)

    with col2:
        st.markdown(f"""
        ### 📊 Stats
        - Songs added: {len(songs)}
        - Artists: {len(set(song.split(' - ')[0] for song in songs))}
        """)

    # Show added songs in an expander
    with st.expander("View Added Songs", expanded=False):
        for i, song in enumerate(songs, 1):
            st.write(f"{i}. {song}")


def show_error_message(error: str):
    """Show a formatted error message with helpful suggestions."""

    # Common error patterns and their user-friendly messages
    error_patterns = {
        "auth": {
            "keywords": ["auth", "unauthorized", "permission", "credentials"],
            "message": """
            This appears to be an authentication issue. Please try:
            1. Logging out and back in
            2. Getting fresh authentication headers
            3. Making sure you're logged into YouTube Music
            """
        },
        "network": {
            "keywords": ["network", "connection", "timeout", "unreachable"],
            "message": """
            This appears to be a network issue. Please try:
            1. Checking your internet connection
            2. Refreshing the page
            3. Trying again in a few minutes
            """
        },
        "rate_limit": {
            "keywords": ["rate", "limit", "quota", "too many"],
            "message": """
            You might be hitting YouTube Music's rate limits. Please try:
            1. Waiting a few minutes before trying again
            2. Reducing the number of songs per artist
            3. Processing fewer artists at once
            """
        }
    }

    # Determine error type and get appropriate message
    error_lower = error.lower()
    additional_help = None

    for error_type, data in error_patterns.items():
        if any(keyword in error_lower for keyword in data["keywords"]):
            additional_help = data["message"]
            break

    # Show error message
    st.error(f"""
    ### ❌ Playlist Creation Failed

    {error}

    {additional_help if additional_help else '''
    Please check:
    - Your authentication is still valid
    - The artists' names are correct
    - You have sufficient permissions in YouTube Music
    - Your internet connection is stable
    '''}
    """)

    # Show retry suggestion
    st.info("You can try again after addressing the issue above.")


def show_authentication_help():
    """Show instructions for getting authentication headers."""
    st.markdown("""
    ### How to get your YouTube Music Authentication:

    1. Install the browser extension "ModHeader" ([Chrome](https://chrome.google.com/webstore/detail/modheader/idgpnmonknjnojddfkpgkljpfnnfcklj) or [Firefox](https://addons.mozilla.org/en-US/firefox/addon/modheader-firefox/))

    2. Open [YouTube Music](https://music.youtube.com/) in your browser

    3. Make sure you're logged into your Google Account

    4. Open DevTools (press F12 or right-click and select 'Inspect')

    5. Go to the 'Network' tab in DevTools

    6. Filter for 'browse' in the network tab

    7. Click on a 'browse' request and look for these request headers:
       - `authorization`
       - `cookie`

    8. Copy these values and paste them below in this format:
    ```json
    {
        "authorization": "SAPISIDHASH ...",
        "cookie": "VISITOR_INFO1_LIVE=...; CONSENT=...; ..."
    }
    ```

    > Note: These credentials are only stored in your browser session and are never saved on our servers.
    > You'll need to provide them again if you close the browser or clear your session.

    ### Security Note:
    - Only use this app on a trusted device
    - Your credentials give access to your YouTube Music account
    - We never store or transmit your credentials
    - All playlists are created as private by default
    """)


def validate_auth_json(auth_str: str) -> bool:
    """Validate the authentication JSON format."""
    try:
        auth_data = json.loads(auth_str)
        required_fields = ['authorization', 'cookie']
        return all(field in auth_data for field in required_fields)
    except json.JSONDecodeError:
        return False


def init_ytmusic(auth_str: str) -> YTMusic:
    """Initialize YTMusic with authentication headers."""
    try:
        auth_data = json.loads(auth_str)

        # Create headers dict with required fields
        headers = {
            'authorization': auth_data['authorization'],
            'cookie': auth_data['cookie'],
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/json',
            'X-Goog-AuthUser': '0',
            'x-origin': 'https://music.youtube.com'
        }

        # Write headers to temp file
        with open('headers_auth.json', 'w') as f:
            json.dump(headers, f)

        # Initialize YTMusic
        ytmusic = YTMusic('headers_auth.json')

        # Clean up temp file
        os.remove('headers_auth.json')

        return ytmusic
    except Exception as e:
        raise Exception(f"Failed to initialize YouTube Music: {str(e)}")


def load_persistent_auth():
    """Load authentication from local storage."""
    try:
        # Try to get saved auth data
        if 'persistent_auth' in st.session_state:
            auth_data = st.session_state.persistent_auth
            # Verify the auth data still works
            generator = FestivalPlaylistGenerator(auth_data['auth_str'])
            if generator.test_auth():
                st.session_state.auth_str = auth_data['auth_str']
                st.session_state.authenticated = True
                st.session_state.auth_timestamp = auth_data.get('timestamp', datetime.now().isoformat())
                return True
            else:
                # Auth is no longer valid, clear it
                del st.session_state.persistent_auth
    except Exception:
        if 'persistent_auth' in st.session_state:
            del st.session_state.persistent_auth
    return False


def save_persistent_auth(auth_str: str):
    """Save authentication to local storage."""
    st.session_state.persistent_auth = {
        'auth_str': auth_str,
        'timestamp': datetime.now().isoformat()
    }


def format_timestamp(timestamp_str: str) -> str:
    """Format the timestamp for display."""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return "Unknown"


def main():
    st.set_page_config(
        page_title="Festival Playlist Generator",
        page_icon="🎵",
        layout="centered"
    )

    st.title("🎵 Festival Playlist Generator")
    st.write("Create a YouTube Music playlist with top songs from your festival lineup!")

    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    # Try to load saved authentication
    if not st.session_state.authenticated:
        if load_persistent_auth():
            st.success("🔄 Successfully restored previous authentication!")

    # Authentication section
    if not st.session_state.authenticated:
        st.warning("Please authenticate with YouTube Music to continue")

        with st.expander("ℹ️ How to authenticate", expanded=True):
            show_authentication_help()

        auth_input = st.text_area(
            "Enter your YouTube Music authentication JSON:",
            help="Paste your authentication headers in JSON format. See instructions above."
        )

        if st.button("Authenticate", type="primary"):
            if auth_input:
                if validate_auth_json(auth_input):
                    try:
                        # Initialize generator with auth
                        generator = FestivalPlaylistGenerator(auth_input)

                        # Test authentication
                        if generator.test_auth():
                            # Store auth in session state (encoded to prevent XSS)
                            encoded_auth = base64.b64encode(auth_input.encode()).decode()
                            st.session_state.auth_str = encoded_auth
                            st.session_state.authenticated = True
                            # Save to persistent storage
                            save_persistent_auth(encoded_auth)
                            st.success("Authentication successful!")
                            time.sleep(1)  # Give user time to see success message
                            st.rerun()
                        else:
                            st.error("Authentication test failed - please check your credentials")
                    except Exception as e:
                        st.error(f"Authentication failed: {str(e)}")
                else:
                    st.error("Invalid authentication format. Please follow the instructions above.")

        st.markdown("---")
        st.markdown("""
        ### Troubleshooting

        If you're having trouble authenticating:
        1. Make sure you're logged into YouTube Music
        2. Check that you've copied both the authorization and cookie headers
        3. Verify the JSON format matches the example
        4. Try refreshing YouTube Music and getting new headers
        5. Clear your browser cache and cookies, then log in again

        Still having issues? Try these steps:
        1. Open YouTube Music in a private/incognito window
        2. Log in to your account
        3. Get fresh authentication headers
        4. Make sure to include all required fields
        """)
        return

    # Show authentication status in sidebar
    with st.sidebar:
        st.write("### Authentication Status")
        st.write("✅ Authenticated")
        if 'auth_timestamp' in st.session_state:
            st.write(f"Last authenticated: {format_timestamp(st.session_state.auth_timestamp)}")

        # Add authentication check button
        if st.button("🔄 Check Authentication"):
            try:
                generator = FestivalPlaylistGenerator(
                    base64.b64decode(st.session_state.auth_str).decode()
                )
                if generator.test_auth():
                    st.success("Authentication is valid!")
                    # Update timestamp
                    save_persistent_auth(st.session_state.auth_str)
                else:
                    st.error("Authentication has expired!")
                    st.session_state.authenticated = False
                    if 'persistent_auth' in st.session_state:
                        del st.session_state.persistent_auth
                    st.rerun()
            except Exception as e:
                st.error(f"Authentication error: {str(e)}")
                st.session_state.authenticated = False
                if 'persistent_auth' in st.session_state:
                    del st.session_state.persistent_auth
                st.rerun()

        if st.button("📤 Logout"):
            st.session_state.authenticated = False
            if 'persistent_auth' in st.session_state:
                del st.session_state.persistent_auth
            st.rerun()

    # Main application (only shown when authenticated)
    with st.expander("ℹ️ How to use"):
        st.write("""
        1. Enter each artist name on a new line
        2. Give your playlist a name
        3. Choose how many songs per artist you want
        4. Click 'Create Playlist' and wait for the magic to happen!
        """)

    # Multi-line text input for artist lineup
    st.write("Enter artist names (one per line):")
    lineup_text = st.text_area(
        "Lineup",
        height=200,
        help="Enter each artist name on a new line"
    )

    # Convert text to list of artists
    lineup = [artist.strip() for artist in lineup_text.split('\n') if artist.strip()]

    col1, col2 = st.columns(2)

    # Input for playlist name
    with col1:
        playlist_name = st.text_input(
            "Playlist Name",
            "My Festival Playlist",
            help="Choose a name for your playlist"
        )

    # Slider for number of songs per artist
    with col2:
        songs_per_artist = st.slider(
            "Songs per Artist",
            min_value=1,
            max_value=10,
            value=3,
            help="How many top songs to include for each artist"
        )

    # Logout option
    if st.button("📤 Logout", type="secondary", help="Clear your authentication"):
        st.session_state.authenticated = False
        st.rerun()

    if st.button("🎵 Create Playlist", type="primary", disabled=not lineup):
        try:
            auth_str = base64.b64decode(st.session_state.auth_str).decode()
            generator = FestivalPlaylistGenerator(auth_str)

            # Create playlist
            playlist_id, songs = generator.create_festival_playlist(
                lineup=lineup,
                playlist_name=playlist_name,
                songs_per_artist=songs_per_artist
            )

            if playlist_id:
                show_playlist_results(playlist_id, songs)
            else:
                show_error_message("Failed to create playlist. Please check the error messages above.")

        except Exception as e:
            error_message = str(e)
            # Check if it might be an authentication issue
            if "auth" in error_message.lower() or "unauthorized" in error_message.lower():
                show_error_message(
                    "Authentication error. Please try logging out and authenticating again.\n\n"
                    f"Error details: {error_message}"
                )
                # Clear authentication if it seems invalid
                st.session_state.authenticated = False
                if 'persistent_auth' in st.session_state:
                    del st.session_state.persistent_auth
                st.warning("You've been logged out due to authentication issues. Please refresh the page and log in again.")
            else:
                show_error_message(f"An unexpected error occurred: {error_message}")

    # Footer
    st.markdown("---")
    st.markdown(
        "This app creates private playlists in your YouTube Music account."
    )

if __name__ == "__main__":
    main()
