#!/bin/bash

# Production deployment script for Hostinger

echo "🚀 Starting deployment..."

# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Install Python 3.9+ if not present
sudo apt install python3 python3-pip python3-venv -y

# 3. Create application directory
sudo mkdir -p /var/www/pl-ai-agent
cd /var/www/pl-ai-agent

# 4. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
pip install -r requirements.txt

# 6. Set up environment variables
cp .env.production .env

# 7. Create systemd service (backend)
sudo tee /etc/systemd/system/pl-ai-agent.service > /dev/null <<EOL
[Unit]
Description=Premier League AI Agent API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/pl-ai-agent
ExecStart=/var/www/pl-ai-agent/venv/bin/uvicorn backend:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=PATH=/var/www/pl-ai-agent/venv/bin

[Install]
WantedBy=multi-user.target
EOL

# 8. Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable pl-ai-agent
sudo systemctl start pl-ai-agent

echo "✅ Deployment complete!"
echo "🔍 Check status: sudo systemctl status pl-ai-agent"