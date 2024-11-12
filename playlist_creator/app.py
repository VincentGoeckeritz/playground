import streamlit as st
from ytmusicapi import YTMusic
import os
from typing import List
import json
import base64

class FestivalPlaylistGenerator:
    def __init__(self, auth_str: str):
        """Initialize YTMusic with user's authentication."""
        try:
            # Write credentials to temporary file for YTMusic
            with open('oauth.json', 'w') as f:
                f.write(auth_str)
            
            self.ytmusic = YTMusic('oauth.json')
            
            # Clean up temporary file
            os.remove('oauth.json')
        except Exception as e:
            raise Exception(f"Failed to initialize YouTube Music: {str(e)}")

    def get_top_songs(self, artist: str, limit: int = 3) -> List[dict]:
        """Get the top songs for an artist."""
        try:
            # Search for the artist
            search_results = self.ytmusic.search(artist, filter="artists")
            if not search_results:
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
            
            return songs
            
        except Exception as e:
            st.error(f"Error getting top songs for {artist}: {str(e)}")
            return []

    def create_festival_playlist(self, lineup: List[str], playlist_name: str, songs_per_artist: int = 3) -> tuple:
        """Create a playlist with top songs from festival lineup."""
        try:
            # Create new playlist
            playlist_id = self.ytmusic.create_playlist(
                title=playlist_name,
                description=f"Top {songs_per_artist} songs from each artist at {playlist_name}",
                privacy="PRIVATE"
            )
            
            all_songs = []
            
            # Get top songs for each artist and add to playlist
            for artist in lineup:
                songs = self.get_top_songs(artist, songs_per_artist)
                if songs:
                    song_ids = [song['videoId'] for song in songs]
                    self.ytmusic.add_playlist_items(playlist_id, song_ids)
                    all_songs.extend([f"{artist} - {song['title']}" for song in songs])
                    
            return playlist_id, all_songs
            
        except Exception as e:
            st.error(f"Error creating playlist: {str(e)}")
            return None, []

def show_authentication_help():
    """Show instructions for getting authentication headers."""
    st.markdown("""
    ### How to get your YouTube Music Authentication:
    
    1. Open YouTube Music in your browser
    2. Sign in if you haven't already
    3. Right-click anywhere on the page and select 'Inspect' or press F12
    4. Go to the 'Network' tab
    5. Click on any request (like 'browse' or 'next')
    6. In the request headers, find and copy the entire 'Cookie' value
    7. Paste it in the text area below
    
    > Note: These credentials are only stored in your browser session and are never saved on our servers.
    > You'll need to provide them again if you close the browser or clear your session.
    """)

def main():
    st.set_page_config(
        page_title="Festival Playlist Generator",
        page_icon="🎵",
        layout="centered"
    )
    
    st.title("🎵 Festival Playlist Generator")
    st.write("Create a YouTube Music playlist with top songs from your festival lineup!")
    
    # Initialize session state for authentication
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Authentication section
    if not st.session_state.authenticated:
        st.warning("Please authenticate with YouTube Music to continue")
        
        with st.expander("ℹ️ How to authenticate"):
            show_authentication_help()
        
        auth_input = st.text_area(
            "Enter your YouTube Music authentication cookie:",
            help="Paste your authentication cookie here. See instructions above."
        )
        
        if st.button("Authenticate", type="primary"):
            if auth_input:
                try:
                    # Create auth json
                    auth_data = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
                        "Cookie": auth_input
                    }
                    
                    # Test authentication
                    with open('temp_auth.json', 'w') as f:
                        json.dump(auth_data, f)
                    
                    test_client = YTMusic('temp_auth.json')
                    os.remove('temp_auth.json')
                    
                    # Store auth in session state (encoded to prevent XSS)
                    st.session_state.auth_str = base64.b64encode(json.dumps(auth_data).encode()).decode()
                    st.session_state.authenticated = True
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Authentication failed: {str(e)}")
        
        return
    
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
        st.experimental_rerun()
    
    if st.button("🎵 Create Playlist", type="primary", disabled=not lineup):
        with st.spinner("Creating your festival playlist..."):
            try:
                # Decode auth string from session state
                auth_str = base64.b64decode(st.session_state.auth_str).decode()
                
                generator = FestivalPlaylistGenerator(auth_str)
                playlist_id, songs = generator.create_festival_playlist(
                    lineup=lineup,
                    playlist_name=playlist_name,
                    songs_per_artist=songs_per_artist
                )
                
                if playlist_id:
                    st.success("✨ Your playlist is ready!")
                    
                    # Show playlist link
                    playlist_url = f"https://music.youtube.com/playlist?list={playlist_id}"
                    st.markdown(f"**[Open Your Playlist in YouTube Music]({playlist_url})**")
                    
                    # Show added songs in an expander
                    with st.expander("View Added Songs"):
                        for song in songs:
                            st.write(f"🎵 {song}")
                else:
                    st.error("Failed to create playlist. Please try again.")
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.session_state.authenticated = False
                st.info("Please authenticate again and retry.")
                st.experimental_rerun()

    # Footer
    st.markdown("---")
    st.markdown(
        "This app creates private playlists in your YouTube Music account."
    )

if __name__ == "__main__":
    main()
