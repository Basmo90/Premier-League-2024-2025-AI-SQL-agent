# 🚀 Hostinger Deployment Guide - Premier League AI Agent

## Prerequisites
- Hostinger Cloud Hosting or VPS plan
- Domain name configured with Hostinger
- SSH access to your server

## 1. Server Setup

### Login to your Hostinger server:
```bash
ssh root@your-server-ip
```

### Update system packages:
```bash
apt update && apt upgrade -y
apt install nginx python3 python3-pip python3-venv git certbot python3-certbot-nginx -y
```

## 2. Deploy Backend

### Clone and setup:
```bash
cd /var/www
git clone https://github.com/yourusername/your-repo-name.git pl-ai-agent
cd pl-ai-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure environment:
```bash
cp .env.production .env
nano .env  # Edit with your actual values
```

### Start backend service:
```bash
chmod +x deploy.sh
./deploy.sh
```

## 3. Deploy Frontend

### Build React app:
```bash
cd frontend
npm install
npm run build
```

### Configure Nginx:
```bash
cp ../nginx.conf /etc/nginx/sites-available/pl-ai-agent
ln -s /etc/nginx/sites-available/pl-ai-agent /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t  # Test configuration
systemctl restart nginx
```

## 4. SSL Certificate

### Install Let's Encrypt SSL:
```bash
certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## 5. Database Security

### Set proper permissions:
```bash
chmod 600 pl_data.db
chown www-data:www-data pl_data.db
```

## 6. Security Checklist

- ✅ Environment variables secured
- ✅ CORS configured for production
- ✅ SSL certificate installed
- ✅ Database file protected
- ✅ API documentation hidden in production
- ✅ Security headers configured
- ✅ Firewall configured (allow only 22, 80, 443)

## 7. Monitoring & Maintenance

### Check service status:
```bash
systemctl status pl-ai-agent
systemctl status nginx
```

### View logs:
```bash
journalctl -u pl-ai-agent -f
tail -f /var/log/nginx/access.log
```

### Update deployment:
```bash
cd /var/www/pl-ai-agent
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm run build
systemctl restart pl-ai-agent
systemctl reload nginx
```

## Troubleshooting

**Backend not starting:**
```bash
journalctl -u pl-ai-agent -n 50
```

**Frontend not loading:**
```bash
nginx -t
tail -f /var/log/nginx/error.log
```

**SSL issues:**
```bash
certbot renew --dry-run
```