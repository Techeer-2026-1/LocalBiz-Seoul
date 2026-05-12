#!/usr/bin/env bash
# AnyWay API — GCE Nginx + Let's Encrypt 1회성 셋업 (nip.io)
#
# 사용법:
#   sudo bash deploy/nginx/setup.sh
#
# 전제조건:
#   1. GCE 방화벽 80/443 인바운드 허용
#      gcloud compute firewall-rules create allow-http-https \
#        --allow tcp:80,tcp:443 --target-tags=http-server
#   2. 이 스크립트를 root 또는 sudo로 실행

set -euo pipefail

# GCE 외부 IP 자동 감지 → nip.io 도메인 생성
EXTERNAL_IP=$(curl -sf http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google" 2>/dev/null \
    || curl -sf https://ifconfig.me)
DOMAIN="${EXTERNAL_IP}.nip.io"

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CONF_SRC="${REPO_DIR}/deploy/nginx/anyway-api.conf"

echo "=== AnyWay Nginx SSL Setup (nip.io) ==="
echo "External IP: ${EXTERNAL_IP}"
echo "Domain:      ${DOMAIN}"
echo "Repo:        ${REPO_DIR}"
echo ""

# 1. nginx + certbot 설치
echo "[1/5] Installing nginx + certbot..."
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx

# 2. ACME 챌린지 디렉터리
echo "[2/5] Creating certbot webroot..."
mkdir -p /var/www/certbot

# 3. 인증서 발급 (standalone — nginx 아직 미설정)
echo "[3/5] Issuing SSL certificate for ${DOMAIN}..."
systemctl stop nginx || true
certbot certonly --standalone -d "${DOMAIN}" --non-interactive --agree-tos --register-unsafely-without-email

# 4. nginx 설정 배포
echo "[4/5] Deploying nginx config..."
cp "${CONF_SRC}" /etc/nginx/sites-available/anyway-api.conf
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
echo "Verify:  curl -I https://${DOMAIN}"
echo "SSE:     curl -N https://${DOMAIN}/api/v1/chat/stream"
echo ""
echo "프론트엔드 환경변수:"
echo "  NEXT_PUBLIC_API_URL=https://${DOMAIN}"
