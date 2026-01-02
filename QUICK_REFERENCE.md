# Portin Quick Reference Card

**For Daily Use**

---

## Starting Porto

```bash
# 1. Open Terminal/Command Prompt
# 2. Go to project folder
cd path/to/portin

# 3. Activate virtual environment
venv\Scripts\activate       # Windows
source venv/bin/activate    # Mac/Linux

# 4. Start dashboard
python run.py

# 5. Open browser
# http://localhost:5000
```

---

## Git Commands

### Check Your Settings
```bash
git config user.name
git config user.email
```

### Set Your Details (One Time)
```bash
git config --local user.name "Your Full Name"
git config --local user.email "your.email@company.com"
```

### Get Latest Code
```bash
git pull origin v1
pip install -r requirements.txt  # In case dependencies changed
```

### Check Status
```bash
git status  # See what changed
git log --oneline -5  # See recent commits
```

---

## Common Tasks

### Export Data
1. Select session from dropdown
2. Click "Export CSV"
3. File downloads automatically

### Clear Session Data
1. Select a session
2. Click "Clear Session"
3. Confirm deletion

### Create New Search
1. Click "+ New Research"
2. Fill in criteria
3. Add reference companies (optional)
4. Choose search engine
5. Click "Start Discovery"

---

## Troubleshooting

### Server Won't Start
```bash
# Check if port is in use
netstat -ano | findstr :5000  # Windows
lsof -i :5000                 # Mac/Linux

# Kill process or use different port
python run.py --port 5001
```

### Virtual Environment Not Working
```bash
# Deactivate and reactivate
deactivate
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
```

### Missing Modules
```bash
# Reinstall dependencies
venv\Scripts\activate
pip install -r requirements.txt
```

---

## API Key Setup

Edit `.env` file:

```bash
# REQUIRED
GEMINI_API_KEY=your_key_here

# RECOMMENDED (for better search)
SERPER_KEY=your_serper_key_here
```

Get keys:
- Gemini: https://aistudio.google.com/app/apikey
- Serper: https://serper.dev

---

## Important Notes

❗ **NEVER commit `.env` file** - it contains your secret keys

✅ **Always activate virtual environment** before running commands

📁 **Exports save to:** `exports/` folder

💾 **Database location:** `database/portin.db`

---

## Getting Help

1. Check terminal for error messages
2. See **SETUP.md** for detailed instructions
3. Ask your team lead

---

**Quick tip:** Keep this file handy - you'll use these commands daily!
