# Festival Playlist Generator

Create YouTube Music playlists with top songs from your festival lineup automatically! Simply paste your lineup, and the app will create a playlist with the most popular songs from each artist.

> [!NOTE]
> This (app and ReadMe) was done mostly by feeding Info to [claude.ai](https://claude.ai), so not all info below might be entirely correct. The app itself is working though, I´ve tested it with my own Youtube Music and a list of bands. Also be cautious with the list of bands, it will just look for the name, if there are multiple artists under that name you might not get what you´re looking for.

## Features

- Create playlists from festival lineups automatically
- Choose number of top songs per artist (1-10 songs)
- Persistent authentication (remembers your login)
- Private playlists in your YouTube Music account
- Simple web interface
- Progress tracking during playlist creation
- Detailed feedback about added songs
- Direct links to created playlists

## Future plans

- add streamlit-googe-auth for OAuth support
- include a way to get the list of bands directly from line-up images

## Live Demo

Visit the app at: [lineup-playlist-creator.streamlit.app](https://lineup-playlist-creator.streamlit.app/)

## Usage

1. **Authenticate with YouTube Music**
   - Open YouTube Music in your browser
   - Make sure you're logged in
   - Open DevTools (F12 or right-click -> Inspect)
   - Go to the 'Network' tab
   - Filter for 'browse'
   - Click on a 'browse' request
   - Find and copy these request headers:
     - `authorization`
     - `cookie`
   - Paste them in JSON format:
   ```json
   {
       "authorization": "SAPISIDHASH ...",
       "cookie": "VISITOR_INFO1_LIVE=...; CONSENT=...; ..."
   }
   ```

2. **Create Your Playlist**
   - Enter your festival lineup (one artist per line)
   - Set a name for your playlist
   - Choose how many songs per artist you want
   - Click "Create Playlist"
   - Wait for the magic to happen!

## Authentication

- Authentication data is stored locally in your browser
- You only need to authenticate once unless you log out
- Authentication status is shown in the sidebar
- You can check authentication validity at any time
- Auto-logout if authentication becomes invalid

## Development

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

### Local Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/festival-playlist-generator.git
cd festival-playlist-generator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run locally:
```bash
streamlit run app.py
```

### Dependencies

Not necessarily in those versions, but those are what´s tested and confirmed working.

- streamlit==1.40.1
- ytmusicapi==1.8.2

## Deployment

This app is designed to be deployed on Streamlit Cloud:

1. Fork this repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Deploy from your forked repository

## Security

- No credentials are stored on the server
- Authentication data is stored only in your browser's local storage
- All playlists are created as private by default
- Authentication data is cleared on logout
- Automatic session cleanup for invalid authentication

## Limitations

- YouTube Music authentication may expire after some time
- Rate limits may apply for many playlist operations
- Some artists might not be found if names don't match exactly
- Authentication needs to be refreshed occasionally
- Private/incognito mode won't persist authentication

## Troubleshooting

If you encounter issues:

1. **Authentication Issues**
   - Try logging out and back in
   - Get fresh authentication headers
   - Make sure you're logged into YouTube Music

2. **Artists Not Found**
   - Check the spelling of artist names
   - Try the official artist name from YouTube Music
   - Remove special characters from names

3. **Playlist Creation Fails**
   - Check your authentication is still valid
   - Try with fewer artists first
   - Check your internet connection
   - Wait a few minutes and try again

## Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Acknowledgments

- [ytmusicapi](https://github.com/sigma67/ytmusicapi) - The awesome API wrapper for YouTube Music
- [Streamlit](https://streamlit.io/) - The incredible framework for building data apps

## Author

Vincent Göckeritz
