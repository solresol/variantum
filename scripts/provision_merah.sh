#!/bin/sh

set -eu

SITE="${SITE:-parallage.symmachus.org}"
APP_USER="${APP_USER:-parallage}"
REMOTE="${REMOTE:-merah}"

ssh "$REMOTE" "set -eu
if ! id '$APP_USER' >/dev/null 2>&1; then
  doas useradd -m -s /usr/local/bin/zsh -c 'Parallage review app' '$APP_USER'
fi
doas mkdir -p '/var/www/vhosts/$SITE/htdocs' '/var/www/vhosts/$SITE/cgi-bin' '/var/www/vhosts/$SITE/db' '/var/www/vhosts/$SITE/etc'
doas chown root:daemon '/var/www/vhosts/$SITE'
doas chmod 755 '/var/www/vhosts/$SITE'
doas chown -R '$APP_USER:daemon' '/var/www/vhosts/$SITE/htdocs' '/var/www/vhosts/$SITE/cgi-bin'
doas chmod 755 '/var/www/vhosts/$SITE/htdocs' '/var/www/vhosts/$SITE/cgi-bin'
doas chown '$APP_USER:www' '/var/www/vhosts/$SITE/db'
doas chmod 775 '/var/www/vhosts/$SITE/db'
doas touch '/var/www/vhosts/$SITE/etc/htpasswd'
doas chown root:www '/var/www/vhosts/$SITE/etc' '/var/www/vhosts/$SITE/etc/htpasswd'
doas chmod 750 '/var/www/vhosts/$SITE/etc'
doas chmod 640 '/var/www/vhosts/$SITE/etc/htpasswd'
"
