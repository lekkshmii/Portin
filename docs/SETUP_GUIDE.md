# Portin Setup Guide

Welcome! Follow these simple steps to set up the Portin project on your Windows machine.

## Prerequisites
1.  **Python 3.10+**: Ensure Python is installed.
    *   Open Terminal (PowerShell or Command Prompt) and type `python --version`.
    *   If not installed, download from [python.org](https://www.python.org/).

## Step 1: Create a Virtual Environment (venv)
A "venv" keeps this project's libraries separate from your other projects.

1.  Open your terminal in the project folder (`portin`).
2.  Run this command:
    ```powershell
    python -m venv venv
    ```
    *(This creates a folder named `venv`)*

## Step 2: Activate the Environment
You need to "turn on" the venv so your computer uses it.

*   **Windows (PowerShell)**:
    ```powershell
    .\venv\Scripts\Activate
    ```
    *(You should see `(venv)` appear at the start of your command line)*

*   **Problem?** If you get a "running scripts is disabled" error, run this first:
    ```powershell
    Set-ExecutionPolicy Unrestricted -Scope Process
    ```
    Then try activating again.

## Step 3: Install Dependencies
Now install all the required tools (Apollo, Gemini, Crawl4AI).

1.  Make sure you are in the `(venv)` (see Step 2).
2.  Run:
    ```powershell
    pip install -r requirements.txt
    ```
3.  Install browser drivers (for scraping):
    ```powershell
    python -m playwright install
    ```

## Step 4: Configure Keys (.env)
1.  Create a file named `.env` in the root folder (if not there).
2.  Add your API keys:
    ```env
    GEMINI_API_KEY=your_gemini_key_here
    APOLLO_API_KEY=your_apollo_key_here
    SERPER_KEY=optional_serper_key
    ```

## Step 5: Test It!
Run the verification script to make sure everything is connected.

```powershell
python verify_deep_research.py
```

If you see **"✅ VERIFICATION SUCCESSFUL"**, you are ready to go!

---

### Common Commands
*   **Run Discovery**: `python run_discovery.py`
*   **Run Deep Dashboard**: `python run_dashboard.py` (Wait for URL to appear)
*   **Run Enrichment**: `python run_enrichment.py`
