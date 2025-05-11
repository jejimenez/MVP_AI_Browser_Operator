#!/bin/bash

# Install Python requirements
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

echo "Setup completed successfully!" 