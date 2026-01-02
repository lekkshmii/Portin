# Group Bayport 3D Globe

This is an interactive 3D globe visualization for Group Bayport locations.

## How to Run

Because this project loads external files (textures and CSV data), you cannot simply open `index.html` directly in your browser due to security restrictions (CORS). You must run a local server.

### Option 1: Using Python (Recommended)
If you have Python installed:
1. Open a terminal/command prompt in this folder.
2. Run: `python -m http.server`
3. Open your browser to `http://localhost:8000`

### Option 2: Using Node.js/Vite
If you prefer Node.js:
1. Run `npx vite` in this folder.
2. Open the URL shown in the terminal.

### Option 3: VS Code Live Server
If you use VS Code, install the "Live Server" extension and click "Go Live" at the bottom right.

## Editing Data
Modify `data.csv` to add or remove locations.
Format: `Company Name,Latitude,Longitude,City,Type`
