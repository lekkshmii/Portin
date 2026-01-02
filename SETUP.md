# Portin Setup Guide

**For Team Members - Step-by-Step Instructions**

This guide will help you set up Portin on your computer, even if you're new to development tools.

---

## Prerequisites

Before starting, make sure you have these installed:

### 1. **Python 3.9 or Higher**

Check if Python is installed:
```bash
python --version
```

If not installed, download from [python.org](https://www.python.org/downloads/)
- **IMPORTANT**: During installation, check "Add Python to PATH"

### 2. **Git**

Check if Git is installed:
```bash
git --version
```

If not installed, download from [git-scm.com](https://git-scm.com/downloads)

---

## Step 1: Get the Code

### Clone the Repository

```bash
# Navigate to where you want the project
cd Desktop

# Clone the project
git clone https://github.com/yourusername/portin.git
cd portin
```

### Configure Git (First Time Only)

Set your name and email for this project:

```bash
# Check current settings
git config user.name
git config user.email

# Set your details (use your real name and company email)
git config --local user.name "Your Full Name"
git config --local user.email "your.email@company.com"
```

---

## Step 2: Set Up Python Environment

### Create a Virtual Environment

A virtual environment keeps this project's dependencies separate from other Python projects.

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your command line when activated.

### Install Dependencies

```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install all required packages
pip install -r requirements.txt

# Install Playwright browser (needed for web scraping)
playwright install chromium
```

This will take a few minutes. Don't worry if you see lots of text scrolling by.

---

## Step 3: Configure API Keys

### Copy the Environment File

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

### Get Your API Keys

Open the `.env` file in a text editor and fill in:

#### 1. **Gemini API Key** (REQUIRED)
- Go to: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
- Click "Create API Key"
- Copy and paste into `.env`:
  ```
  GEMINI_API_KEY=your_actual_key_here
  ```

#### 2. **Serper API Key** (Recommended)
- Go to: [https://serper.dev](https://serper.dev)
- Sign up (free tier: 2,500 searches/month)
- Copy your API key and add to `.env`:
  ```
  SERPER_KEY=your_serper_key_here
  ```

**Note:** If you skip this, the app will use DuckDuckGo instead (slower but free).

---

## Step 4: Test the Installation

### Start the Dashboard

```bash
python run.py
```

You should see:
```
Starting Portin Dashboard...
   Theme: Glassmorphism (Bayport Style)
   URL:   http://localhost:5000

Press Ctrl+C to stop.
```

### Open in Browser

Go to: **http://localhost:5000**

You should see the Porto dashboard!

---

## Daily Usage

### Starting the Server

1. Open Terminal/Command Prompt
2. Navigate to project:
   ```bash
   cd path/to/portin
   ```
3. Activate virtual environment:
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Mac/Linux
   source venv/bin/activate
   ```
4. Start server:
   ```bash
   python run.py
   ```
5. Open browser: http://localhost:5000

### Stopping the Server

Press `Ctrl+C` in the terminal

---

## Updating from Git

When the code is updated, pull the latest changes:

```bash
# Make sure you're in the project folder
cd portin

# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Get latest code
git pull origin v1

# Install any new dependencies
pip install -r requirements.txt
```

---

## Troubleshooting

### "Python is not recognized"

**Fix:** Add Python to your PATH
1. Search for "Environment Variables" in Windows
2. Click "Edit the system environment variables"
3. Click "Environment Variables" button
4. Add Python installation path to PATH

### "playwright install chromium" fails

**Fix:** Run as administrator or with sudo:
```bash
# Windows (run PowerShell as Admin)
playwright install chromium

# Mac/Linux
sudo playwright install chromium
```

### "Module not found" errors

**Fix:** Make sure virtual environment is activated and reinstall:
```bash
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Port 5000 already in use

**Fix:** Stop the other process or use a different port:
```bash
# Use port 5001 instead
python run.py --port 5001
```

Then go to: http://localhost:5001

---

## Getting Help

### Check the Logs

When something goes wrong, check the terminal where you ran `python run.py` - errors will appear there.

### Common Issues

1. **No companies found?**
   - Check your Gemini API key in `.env`
   - Try using reference companies in the search criteria

2. **Slow searches?**
   - Add a Serper API key for faster Google searches
   - Or use "Google Grounding" (doesn't need Serper)

3. **Website not loading?**
   - Make sure the server is running (`python run.py`)
   - Check browser console (F12) for errors
   - Try a different browser

---

## Project Structure

```
portin/
├── dashboard/          # Web interface (Porto UI)
├── discovery/          # Company discovery engine
├── enrichment/         # Company data enrichment
├── intake/             # Search criteria builder
├── sources/            # API integrations
├── data/               # Database (SQLite)
├── output/             # Exported files
├── run.py              # Main dashboard launcher
├── requirements.txt    # Python dependencies
└── .env                # Your API keys (DO NOT COMMIT)
```

---

## Security Notes

### NEVER commit `.env` file to Git!

The `.gitignore` file already prevents this, but double-check:

```bash
# This should show .env is ignored
git status
```

If you see `.env` in changes, DO NOT commit it. It contains your secret API keys.

---

## Using the Dashboard

### 1. **Create a Session**
- Click "+ New Research"
- Fill in your search criteria
- Add reference companies (optional but recommended)

### 2. **Run Discovery**
- Choose a search engine (Google Grounding is recommended)
- Click "Start Discovery"
- Watch real-time log updates

### 3. **Export Results**
- Select your session from the dropdown
- Click "Export CSV" to download

### 4. **Clear Session Data**
- Select a session
- Click "Clear Session" to remove companies (keeps the session)
- Or go to Settings → "Reset Database" to clear everything

---

<div align="center">

**Ready to start?** Run `python run.py` and go to http://localhost:5000

Need help? Ask your team lead or check the troubleshooting section above.

</div>
