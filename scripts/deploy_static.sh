#!/bin/sh

set -eu

SITE="${SITE:-parallage.symmachus.org}"
APP_USER="${APP_USER:-parallage}"
REMOTE="${REMOTE:-merah}"
LOCAL_SITE="${LOCAL_SITE:-site}"
REMOTE_TMP="/tmp/${SITE}.site.$$"
REMOTE_HTDOCS="/var/www/vhosts/$SITE/htdocs"

if [ ! -d "$LOCAL_SITE" ]; then
    echo "Missing $LOCAL_SITE; run scripts/generate_stephanos_review_site.py first." >&2
    exit 1
fi

ssh "$REMOTE" "rm -rf '$REMOTE_TMP' && mkdir -p '$REMOTE_TMP'"
rsync -az --delete "$LOCAL_SITE"/ "$REMOTE:$REMOTE_TMP"/
ssh "$REMOTE" "set -eu
doas mkdir -p '$REMOTE_HTDOCS'
doas rsync -a --delete '$REMOTE_TMP'/ '$REMOTE_HTDOCS'/
doas chown -R '$APP_USER:daemon' '$REMOTE_HTDOCS'
rm -rf '$REMOTE_TMP'
"
