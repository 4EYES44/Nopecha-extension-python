# Nopecha Extension Python

A Python utility for patching a locally downloaded **Nopecha Chrome Extension** by automatically injecting your API key into all required JavaScript, HTML, and config files.

This package is built on top of `chrome_extension_python` and allows you to

- Load your own downloaded Chrome extension folder
- Inject your API key into all related files
- Patch `.js`, `.html`, and `manifest.json`
- Prepare the extension for Selenium, Botasaurus, or manual Chrome loading

### Here is the link to Download The Extension : [NopeCHA_Extension](https://developers.nopecha.com/guides/extension_advanced/#automation-build)

---

## Note . You Should Download The chromium_automation.zip

Here You Can Find The Package In [PyPi](https://pypi.org/project/nopecha-extension/)

## ✨ Features

- This package allows the use of Chrome extensions in Botasaurus, Selenium, and Playwright frameworks.
- 🔐 Just Modify Your "manifest.json" File
- 🔍 Detects placeholders like:
  - `apiKey: ''`
  - `api_key: ""`
  - `NOPECHA_API_KEY`
- 🛠 Updates manifest.json (permissions, storage, etc.)
- ⚡ Easy integration with Selenium, Botasaurus, or Playwright

---

## 📦 Installation

### Install packages using pip:

```bash
pip install chrome_extension_python
pip install nopecha-extension
```

---

## 🚀 Usage Example

```python
from nopecha_extension import Nopecha


API_KEY = "YOUR_NOPECHA_KEY"
EXT_PATH = r"C:/path/to/your/nopecha_extension_folder" # here you can edit your "manifest.json" as you want

# Initialize patcher
ext = Nopecha(api_key=API_KEY)
ext.extension_path = EXT_PATH

# Your Browser Lib (eg.selenium, puppeteer, playwright)
```
