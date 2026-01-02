# Conda Setup Guide for Portin

If standard python venv is failing, **Conda is the best alternative**. It handles installations much better on Windows.

## Prerequisite
Ensure you have **Anaconda** or **Miniconda** installed.
*(If not, download "Miniconda for Windows 64-bit": https://docs.conda.io/en/latest/miniconda.html)*

---

## Step 1: Create the Environment
Open your **Anaconda Prompt** (or powershell if conda is in path) and run:

```powershell
# 1. Create a clean environment named 'portin' with Python 3.10
conda create -n portin python=3.10 -y

# 2. Activate it
conda activate portin
```

## Step 2: Install Dependencies
We will use the `pip` inside Conda to install our specific libraries.

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browsers (for scraping)
playwright install
```

## Step 3: Run the Project
Now you are ready to go.

```powershell
# Verify everything works
python verify_deep_research.py

# Run the pipeline
python run_pipeline.py
```

## Troubleshooting
*   **"Conda not found"**: Make sure you are using the "Anaconda Prompt" application from your Start Menu, not just the standard command prompt.
*   **Playwright error**: If it says "playwright not found", run `pip install playwright` then `playwright install`.

## Bonus: Make Conda Default in VS Code

You don't need to open a separate window! You can make VS Code use your Conda environment automatically.

1.  **Select Interpreter**:
    *   Press `Ctrl + Shift + P`
    *   Type: **"Python: Select Interpreter"**
    *   Choose the one that says `('portin': conda)`

2.  **Set Terminal Default**:
    *   Press `Ctrl + Shift + P`
    *   Type: **"Terminal: Select Default Profile"**
    *   Choose **"Command Prompt"** (Conda often works best with CMD on Windows).

Now, whenever you open a new terminal in VS Code (`Ctrl + ~`), it should automatically activate your `(portin)` environment!
