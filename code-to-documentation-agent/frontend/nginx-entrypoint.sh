#!/bin/sh
set -euo pipefail

if [ -f "/usr/share/nginx/html/env-config.js.template" ]; then
  envsubst '${BUILD_AI_FRONTEND_URL} ${REACT_APP_FULL_ACCESS_PROJECTS} ${REACT_APP_ITEMS_PER_PAGE}' \
    < /usr/share/nginx/html/env-config.js.template \
    > /usr/share/nginx/html/env-config.js
fi

exec nginx -g 'daemon off;'
