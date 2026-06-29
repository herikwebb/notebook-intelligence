#!/usr/bin/env bash
set -euo pipefail

echo "Reviewing PR #${PR_NUMBER} in ${REPO}"
echo "Base: ${BASE_SHA}"
echo "Head: ${HEAD_SHA}"

CHANGED_FILES="$(git diff --name-only "${BASE_SHA}" "${HEAD_SHA}")"

BODY=$(cat <<EOF
## Automated PR Review

I reviewed the latest changes in this PR.

Changed files:

\`\`\`
${CHANGED_FILES}
\`\`\`

Review result:

- No automated findings yet.
- This is a placeholder reviewer. Replace \`scripts/review-pr.sh\` with your real review logic.
EOF
)

gh pr comment "${PR_NUMBER}" \
  --repo "${REPO}" \
  --body "${BODY}"
