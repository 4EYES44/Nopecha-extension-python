

# Nopecha Extension Python

  

A Python utility for patching a locally downloaded **Nopecha Chrome Extension** by automatically injecting your API key into all required JavaScript, HTML, and config files.

  

This package is built on top of `chrome_extension_python` and allows you to

- Load your own downloaded Chrome extension folder

- Inject your API key into all related files

- Patch `.js`, `.html`, and `manifest.json`

- Prepare the extension for Selenium, Botasaurus, or manual Chrome loading


##### Here is the link to Download The Extenstion [https://developers.nopecha.com/guides/extension_advanced/#automation-build](Nopecha Enxtenstion)

## Note . You Should Download The chromium_automation.zip 

  

---

  

## ✨ Features

  

-  This package allows the use of Chrome extensions in Botasaurus, Selenium, and Playwright frameworks.

- 🔐 Just Modify Your "mainfest.json" File

- 🔍 Detects placeholders like:

  - `apiKey: ''`

  - `api_key: ""`

  - `NOPECHA_API_KEY`


- 🛠 Updates manifest.json (permissions, storage, etc.)  

- ⚡ Easy integration with Selenium, Botasaurus, or Chrome

  

---

  

## 📦 Installation

  install packages using pip:

  

```bash

pip install chrome_extension_python

pip install nopecha-extension

````

  
  
---

## 🚀 Usage Example

```


from nopecha_extension import Nopecha

from botasaurus.browser import browser, Driver

  

API_KEY = "YOUR_NOPECHA_KEY"

EXT_PATH = r"C:/path/to/your/nopecha_extension_folder" # here you can edit your "mainfest.json" as you want

  

# Initialize patcher

ext = Nopecha(api_key=API_KEY)

ext.extension_path = EXT_PATH

  

@browser(

  

    extensions=[ext],

  

    )

```


  
