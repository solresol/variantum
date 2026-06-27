#!/bin/sh

set -eu

SITE="${SITE:-parallage.symmachus.org}"
REMOTE="${REMOTE:-merah}"

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 gregb shirley vanessa" >&2
    exit 1
fi

quoted_users=""
for username in "$@"; do
    quoted_users="$quoted_users '$username'"
done

ssh -t "$REMOTE" "set -eu
HTPASSWD='/var/www/vhosts/$SITE/etc/htpasswd'
doas mkdir -p '/var/www/vhosts/$SITE/etc'
doas touch \"\$HTPASSWD\"
doas chown root:www '/var/www/vhosts/$SITE/etc' \"\$HTPASSWD\"
doas chmod 750 '/var/www/vhosts/$SITE/etc'
doas chmod 640 \"\$HTPASSWD\"
for username in $quoted_users; do
  if doas test -s \"\$HTPASSWD\"; then
    doas htpasswd \"\$HTPASSWD\" \"\$username\"
  else
    doas htpasswd -c \"\$HTPASSWD\" \"\$username\"
  fi
done
"
