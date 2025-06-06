import os
from datetime import datetime
from typing import List
import json
import base64
import time
import tempfile
import re

import streamlit as st
from ytmusicapi import YTMusic
import google.oauth2.credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import google.auth.exceptions

# OAuth 2.0 configuration
CLIENT_ID = st.secrets.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = st.secrets.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = st.secrets.get("REDIRECT_URI", "http://localhost:8501")

SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.readonly'
]

class FestivalPlaylistGenerator:
    def __init__(self, credentials: google.oauth2.credentials.Credentials):
        """Initialize YTMusic with OAuth2 credentials.

        Args:
            credentials: Google OAuth2 credentials object
        """
        try:
            # Create a temporary file for OAuth headers
            oauth_headers = self._create_oauth_headers(credentials)

            # Write headers to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(oauth_headers, f)
                temp_file = f.name

            # Initialize YTMusic
            self.ytmusic = YTMusic(temp_file)

            # Clean up temp file
            os.remove(temp_file)

            self.last_request_time = 0
            self.min_request_interval = 0.1  # 100ms between requests

        except Exception as e:
            raise Exception(f"Failed to initialize YouTube Music: {str(e)}")

    def _rate_limit(self):
        """Simple rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()

    def _create_oauth_headers(self, credentials: google.oauth2.credentials.Credentials) -> dict:
        """Create headers dict from OAuth2 credentials."""
        # Ensure token is fresh
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        headers = {
            'authorization': f'Bearer {credentials.token}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/json',
            'X-Goog-AuthUser': '0',
            'x-origin': 'https://music.youtube.com'
        }

        return headers

    def get_top_songs(self, artist: str, limit: int = 3) -> List[dict]:
        """Get the top songs for an artist."""
        # Validate inputs
        if not artist or len(artist.strip()) < 2:
            return []

        if limit < 1 or limit > 10:
            limit = 3

        # Add rate limiting
        self._rate_limit()

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


def get_oauth_flow():
    """Create and return OAuth flow object."""
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI]
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    return flow


def handle_oauth_callback():
    """Handle OAuth callback and exchange code for credentials."""
    try:
        # Get all query parameters for debugging
        all_params = dict(st.query_params)
        st.write("**OAuth Callback Debug Info:**")
        st.write(f"All query parameters: {all_params}")

        # Check for OAuth errors first
        error = st.query_params.get("error")
        if error:
            error_description = st.query_params.get("error_description", "No description provided")
            st.error(f"**OAuth Error:** {error}")
            st.error(f"**Description:** {error_description}")
            return None

        # Get authorization code
        code = st.query_params.get("code")
        if not code:
            st.warning("No authorization code received in callback")
            return None

        st.info(f"Received authorization code: {code[:10]}...")

        # Exchange code for credentials
        flow = get_oauth_flow()
        st.info("Attempting to exchange code for credentials...")

        flow.fetch_token(code=code)
        st.success("Successfully exchanged code for credentials!")

        return flow.credentials

    except Exception as e:
        st.error(f"OAuth callback error: {str(e)}")
        st.exception(e)  # Show full traceback
        return None


def save_credentials(credentials: google.oauth2.credentials.Credentials):
    """Save credentials to session state."""
    st.session_state.credentials = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'expiry': credentials.expiry.isoformat() if credentials.expiry else None
    }
    st.session_state.authenticated = True


def load_credentials() -> google.oauth2.credentials.Credentials:
    """Load credentials from session state."""
    if 'credentials' in st.session_state:
        cred_dict = st.session_state.credentials
        expiry = datetime.fromisoformat(cred_dict['expiry']) if cred_dict['expiry'] else None

        credentials = google.oauth2.credentials.Credentials(
            token=cred_dict['token'],
            refresh_token=cred_dict['refresh_token'],
            token_uri=cred_dict['token_uri'],
            client_id=cred_dict['client_id'],
            client_secret=cred_dict['client_secret'],
            scopes=cred_dict['scopes'],
            expiry=expiry
        )

        return credentials
    return None


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


def show_google_signin():
    """Show Google Sign-In interface."""
    st.markdown("""
    ### 🔐 Sign in with Google

    To create playlists in your YouTube Music account, you need to sign in with your Google account.

    **What permissions do we need?**
    - Access to your YouTube account
    - Ability to create and manage playlists
    - Read access to search for songs and artists

    **Your privacy is important:**
    - We only access what's needed to create playlists
    - Your credentials are stored securely in your browser session
    - We never store your personal information on our servers
    """)

    # Check if OAuth is properly configured
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("""
        **OAuth Configuration Missing**

        The app administrator needs to configure Google OAuth credentials.
        Please contact the app administrator to set up:
        - `GOOGLE_CLIENT_ID`
        - `GOOGLE_CLIENT_SECRET`
        - `REDIRECT_URI`

        These should be added to the Streamlit secrets.
        """)
        return

    # Create OAuth flow and get authorization URL
    try:
        flow = get_oauth_flow()
        auth_url, _ = flow.authorization_url(
            prompt='consent',
            access_type='offline',
            include_granted_scopes='true'
        )

        st.markdown("Click the button below to sign in with your Google account:")

        # Use st.link_button for reliable redirect
        st.link_button(
            "🔑 Sign in with Google",
            auth_url,
            type="primary"
        )

        st.info("👆 Click the button above to be redirected to Google's sign-in page. After signing in, you'll be automatically redirected back to this app.")

        # Show debug info in expander for troubleshooting
        with st.expander("🔍 Troubleshooting"):
            st.markdown("""
            **If the sign-in doesn't work:**
            1. Make sure you allow pop-ups for this site
            2. Try using the direct link below
            3. Check that you're using a supported browser
            """)

            st.markdown(f"**Direct link:** [Sign in with Google]({auth_url})")

    except Exception as e:
        st.error(f"Failed to create sign-in link: {str(e)}")
        st.exception(e)  # Show full traceback


def sanitize_artist_name(artist: str) -> str:
    """Sanitize artist name for safe API usage."""
    if not artist:
        return ""

    # Remove excessive whitespace
    artist = artist.strip()

    # Limit length (YouTube searches work best with reasonable lengths)
    artist = artist[:100]

    # Remove potentially problematic characters but keep international chars
    # Keep letters, numbers, spaces, common punctuation in artist names
    artist = re.sub(r'[^\w\s\-\'\.\&\(\)]', '', artist, flags=re.UNICODE)

    # Remove excessive spaces
    artist = re.sub(r'\s+', ' ', artist)

    return artist.strip()


def validate_lineup(lineup_text: str) -> tuple[list[str], list[str]]:
    """Validate and sanitize the lineup text."""
    lines = lineup_text.split('\n')

    # Limit number of artists to prevent API abuse
    MAX_ARTISTS = 50
    if len(lines) > MAX_ARTISTS:
        st.warning(f"Too many artists! Limited to first {MAX_ARTISTS} entries.")
        lines = lines[:MAX_ARTISTS]

    valid_artists = []
    warnings = []

    for i, line in enumerate(lines, 1):
        original = line.strip()
        if not original:
            continue

        sanitized = sanitize_artist_name(original)

        if not sanitized:
            warnings.append(f"Line {i}: '{original}' contains no valid characters")
            continue

        if len(sanitized) < 2:
            warnings.append(f"Line {i}: '{original}' too short after cleaning")
            continue

        if sanitized != original:
            warnings.append(f"Line {i}: Cleaned '{original}' → '{sanitized}'")

        valid_artists.append(sanitized)

    return valid_artists, warnings


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

    # Handle OAuth callback
    if st.query_params.get("code") and not st.session_state.authenticated:
        with st.spinner("Completing sign-in..."):
            credentials = handle_oauth_callback()
            if credentials:
                save_credentials(credentials)
                st.success("✅ Successfully signed in!")
                # Clear URL parameters
                st.query_params.clear()
                time.sleep(1)
                st.rerun()

    # Check if user is authenticated
    if not st.session_state.authenticated:
        show_google_signin()
        return

    # Load credentials and verify they're still valid
    credentials = load_credentials()
    if not credentials:
        st.session_state.authenticated = False
        st.rerun()

    # Refresh token if needed
    try:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            save_credentials(credentials)
    except google.auth.exceptions.RefreshError:
        st.error("Your session has expired. Please sign in again.")
        st.session_state.authenticated = False
        if st.button("Sign in again"):
            st.rerun()
        return

    # Show authentication status in sidebar
    with st.sidebar:
        st.write("### Authentication Status")
        st.write("✅ Signed in with Google")

        if st.button("🔄 Check Connection"):
            try:
                generator = FestivalPlaylistGenerator(credentials)
                if generator.test_auth():
                    st.success("Connection is working!")
                else:
                    st.error("Connection failed!")
            except Exception as e:
                st.error(f"Connection error: {str(e)}")

        if st.button("📤 Sign Out"):
            st.session_state.authenticated = False
            if 'credentials' in st.session_state:
                del st.session_state.credentials
            st.query_params.clear()
            st.rerun()

    # Main application
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
        help="Enter each artist name on a new line (max 50 artists)"
    )

    # Validate and sanitize lineup
    if lineup_text.strip():
        lineup, warnings = validate_lineup(lineup_text)

        # Show warnings if any
        if warnings:
            with st.expander("⚠️ Input Warnings", expanded=False):
                for warning in warnings:
                    st.warning(warning)
    else:
        lineup = []

    # Show artist count
    if lineup:
        st.info(f"Found {len(lineup)} valid artists")

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

    if st.button("🎵 Create Playlist", type="primary", disabled=not lineup):
        try:
            generator = FestivalPlaylistGenerator(credentials)

            # Create playlist
            playlist_id, songs = generator.create_festival_playlist(
                lineup=lineup,
                playlist_name=playlist_name,
                songs_per_artist=songs_per_artist
            )

            if playlist_id:
                show_playlist_results(playlist_id, songs)
            else:
                st.error("Failed to create playlist. Please check the error messages above.")

        except Exception as e:
            error_message = str(e)
            # Check if it might be an authentication issue
            if any(keyword in error_message.lower() for keyword in ["auth", "unauthorized", "permission", "credentials"]):
                st.error(f"""
                **Authentication Error**

                {error_message}

                Please try signing out and signing in again.
                """)

                if st.button("Sign out and try again"):
                    st.session_state.authenticated = False
                    if 'credentials' in st.session_state:
                        del st.session_state.credentials
                    st.rerun()
            else:
                st.error(f"An unexpected error occurred: {error_message}")

    # Footer
    st.markdown("---")
    st.markdown(
        "This app creates private playlists in your YouTube Music account using secure Google Sign-In."
    )


if __name__ == "__main__":
    main()
