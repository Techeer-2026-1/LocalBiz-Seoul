#!/usr/bin/env bash
# AnyWay API — GCE Nginx + Let's Encrypt 1회성 셋업
#
# 사용법:
#   sudo bash deploy/nginx/setup.sh <도메인>
#
# 전제조건:
#   1. 도메인 A 레코드 → 이 서버의 외부 IP
#   2. GCE 방화벽 80/443 인바운드 허용
#      gcloud compute firewall-rules create allow-http-https \
#        --allow tcp:80,tcp:443 --target-tags=http-server
#   3. 이 스크립트를 root 또는 sudo로 실행

set -euo pipefail

DOMAIN="${1:?Usage: sudo bash setup.sh <domain>}"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CONF_SRC="${REPO_DIR}/deploy/nginx/anyway-api.conf"

echo "=== AnyWay Nginx SSL Setup ==="
echo "Domain: ${DOMAIN}"
echo "Repo:   ${REPO_DIR}"
echo ""

# 1. nginx + certbot 설치
echo "[1/5] Installing nginx + certbot..."
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx

# 2. ACME 챌린지 디렉터리
echo "[2/5] Creating certbot webroot..."
mkdir -p /var/www/certbot

# 3. 인증서 발급 (standalone — nginx 아직 미설정)
echo "[3/5] Issuing SSL certificate..."
systemctl stop nginx || true
certbot certonly --standalone -d "${DOMAIN}" --non-interactive --agree-tos --register-unsafely-without-email

# 4. nginx 설정 배포
echo "[4/5] Deploying nginx config..."
sed "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" "${CONF_SRC}" > /etc/nginx/sites-available/anyway-api.conf
ln -sf /etc/nginx/sites-available/anyway-api.conf /etc/nginx/sites-enabled/anyway-api.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t

# 5. nginx 시작 + certbot 자동갱신 확인
echo "[5/5] Starting nginx..."
systemctl enable nginx
systemctl start nginx

# certbot 자동갱신 타이머 확인 (systemd)
if systemctl list-timers | grep -q certbot; then
    echo "Certbot auto-renewal timer: active"
else
    echo "Adding certbot renewal cron..."
    echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'" | crontab -
fi

echo ""
echo "=== Setup complete ==="
echo "Verify: curl -I https://${DOMAIN}"
echo "SSE:    curl -N https://${DOMAIN}/api/v1/chat/stream"
