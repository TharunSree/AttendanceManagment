#!/bin/bash

# A simple script to update the Django application

echo "Starting application update..."

# Make sure we are in the script's directory
cd "$(dirname "$0")"

# Activate the virtual environment
# Replace '.venv' with the name of your virtual environment directory if it's different
source .venv/bin/activate
echo "Virtual environment activated."

# Pull the latest changes from the Git repository's main branch
echo "Pulling latest changes from Git..."
git pull origin website-server
if [ $? -ne 0 ]; then
    echo "Error pulling from Git. Aborting."
    exit 1
fi

# Install or update Python packages
echo "Installing/updating Python packages..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error installing packages. Aborting."
    exit 1
fi

# Apply any new database migrations
echo "Applying database migrations..."
python manage.py migrate
if [ $? -ne 0 ]; then
    echo "Error applying migrations. Aborting."
    exit 1
fi

# Collect all static files
echo "Collecting static files..."
python manage.py collectstatic --noinput
if [ $? -ne 0 ]; then
    echo "Error collecting static files. Aborting."
    exit 1
fi

# --- IMPORTANT ---
# The final step is to restart the application server (e.g., Gunicorn).
# The command for this depends on how you set up your server.
# Below is a common example using systemd.
# You will need to replace 'gunicorn.service' with the actual name of your service file.

echo "Restarting the application server..."
# sudo systemctl restart gunicorn.service  # <--- UNCOMMENT AND EDIT THIS LINE ON YOUR SERVER

echo "-------------------------------------"
echo "Application update completed successfully."
echo "-------------------------------------"
