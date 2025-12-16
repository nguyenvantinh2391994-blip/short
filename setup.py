from setuptools import setup, find_packages

setup(
    name="short-video-creator",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "gspread>=6.1.2",
        "oauth2client>=4.1.3",
        "google-auth-oauthlib>=1.2.0",
        "requests>=2.32.3",
        "click>=8.1.7",
        "rich>=13.9.2",
        "python-dotenv>=1.0.1",
        "watchdog>=4.0.2",
        "Pillow>=10.4.0",
    ],
    entry_points={
        "console_scripts": [
            "short-video=src.main:main",
        ],
    },
    python_requires=">=3.8",
    author="Your Name",
    description="Tool tạo video short tự động cho Facebook và TikTok",
)
