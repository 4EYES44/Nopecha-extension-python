# Nopecha Extension Patcher

A Python utility for patching a locally downloaded **Nopecha Chrome Extension** by automatically injecting your API key into all required JavaScript, HTML, and config files.

This package is built on top of `chrome_extension_python` and allows you to:

- Load your own downloaded Chrome extension folder
- Inject your API key into all related files
- Patch `.js`, `.html`, and `manifest.json`
- Prepare the extension for Selenium, Botasaurus, or manual Chrome loading

---

## ✨ Features

- 🔧 Automatically scans all `.js` files  
- 🔐 Injects API key into config patterns  
- 🔐 Just Modify Your "mainfest.json" File 
- 🔍 Detects placeholders like:
  - `apiKey: ''`
  - `api_key: ""`
  - `NOPECHA_API_KEY`
  - `return e.defaultConfig`
- 🛠 Updates manifest.json (permissions, storage, etc.)  
- ⚡ Easy integration with Selenium, Botasaurus, or Chrome

---

## 📦 Installation

Once you build the package (or after publishing):

```bash
pip install nopecha-extension

## 🚀 Usage Example


from nopecha_extension import Nopecha
from botasaurus.browser import browser, Driver

API_KEY = "YOUR_NOPECHA_KEY"
EXT_PATH = r"C:/path/to/your/nopecha_extension_folder"

# Initialize patcher
ext = Nopecha(api_key=API_KEY)
ext.extension_path = EXT_PATH

@browser(

    extensions=[ext],
    

    
    )

