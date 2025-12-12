from setuptools import setup, find_packages

setup(
    name="nopecha-extension",
    version="0.0.1",
    description="Nopecha extension",
    author="4EYES",
    packages=find_packages(),
    install_requires=[
        "chrome_extension_python",
    ],
    python_requires=">=3.7",
)