#!/bin/sh

set -eu

SITE="${SITE:-parallage.symmachus.org}"
APP_USER="${APP_USER:-parallage}"
REMOTE="${REMOTE:-merah}"
REMOTE_SRC="/home/$APP_USER/variantum/cgi"
REMOTE_TMP="/tmp/${SITE}.cgi.$$"
REMOTE_CGI="/var/www/vhosts/$SITE/cgi-bin"
REMOTE_DB="/var/www/vhosts/$SITE/db/reviews.db"

ssh "$REMOTE" "rm -rf '$REMOTE_TMP' && mkdir -p '$REMOTE_TMP'"
rsync -az --delete cgi/ "$REMOTE:$REMOTE_TMP"/
ssh "$REMOTE" "set -eu
doas mkdir -p '$REMOTE_SRC' '$REMOTE_CGI' '/var/www/vhosts/$SITE/db'
doas rsync -a --delete '$REMOTE_TMP'/ '$REMOTE_SRC'/
doas chown -R '$APP_USER:$APP_USER' '$REMOTE_SRC'
cd '$REMOTE_SRC'
doas -u '$APP_USER' go mod download
for prog in review-save review-state review-status; do
  (cd \"\$prog\" && doas -u '$APP_USER' go build -o \"\$prog.cgi\" .)
  doas install -m 755 -o '$APP_USER' -g daemon \"\$prog/\$prog.cgi\" '$REMOTE_CGI/'
done
doas sqlite3 '$REMOTE_DB' < '$REMOTE_SRC/schema.sql'
doas chown '$APP_USER:www' '/var/www/vhosts/$SITE/db' '$REMOTE_DB'
doas chmod 775 '/var/www/vhosts/$SITE/db'
doas chmod 664 '$REMOTE_DB'
rm -rf '$REMOTE_TMP'
"
