#!/usr/bin/env bash
# Builds the static site and publishes it to AWS Amplify Hosting (manual deployment, no Git connection).
set -euo pipefail
cd "$(dirname "$0")"

set -a; source ../.env; set +a
AWS="${AWS_CLI:-aws}"
BRANCH=main

npm run build
# Kept inside the project: on Windows, Git Bash's /tmp and native Python's /tmp are different folders.
mkdir -p .deploy
ZIP=.deploy/site.zip
python -c "import shutil; shutil.make_archive('.deploy/site', 'zip', 'out')"

read -r JOB URL < <("$AWS" amplify create-deployment --app-id "$AMPLIFY_APP_ID" --branch-name "$BRANCH" \
  --query '[jobId, zipUploadUrl]' --output text | tr -d '\r')
curl -sf -X PUT -H "Content-Type: application/zip" --upload-file "$ZIP" "$URL"
"$AWS" amplify start-deployment --app-id "$AMPLIFY_APP_ID" --branch-name "$BRANCH" --job-id "$JOB" >/dev/null

while :; do
  STATUS=$("$AWS" amplify get-job --app-id "$AMPLIFY_APP_ID" --branch-name "$BRANCH" --job-id "$JOB" --query job.summary.status --output text | tr -d '\r')
  [[ "$STATUS" == PENDING || "$STATUS" == RUNNING ]] || break
  sleep 3
done
echo "Deploy $STATUS: https://$BRANCH.$AMPLIFY_APP_ID.amplifyapp.com"
[[ "$STATUS" == SUCCEED ]]
