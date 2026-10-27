#!/usr/bin/env bash
# Keyless, read-only Google Analytics access for this repository's GitHub Actions.
#
# Run once in Google Cloud Shell (https://shell.cloud.google.com), signed in to the
# Google account that owns the Full Time Google Analytics property:
#
#   bash ga4-github-setup.sh <google-cloud-project-id>
#
# It creates no key, secret or refresh token. GitHub Actions proves who it is with
# its own short-lived identity token; Google accepts that only from
# krishanraja/growth-fulltime on its main branch, and hands back a ten-minute token
# that can only read Analytics. Running it twice changes nothing.
#
# Afterwards, two things by hand (docs/GA4-ACCESS.md, route A):
#   1. Google Analytics, Admin, Property access management: add the service account
#      email this script prints, with the Viewer role and nothing more.
#   2. GitHub, this repository, Settings, Secrets and variables, Actions, Variables:
#      add the three variables this script prints. They are not secrets.
set -euo pipefail

PROJECT_ID="${1:?usage: bash ga4-github-setup.sh <google-cloud-project-id>}"
REPO="krishanraja/growth-fulltime"
OWNER_ID="226431269"            # krishanraja's numeric GitHub ID: a renamed or re-registered account cannot match
POOL="github-actions"
PROVIDER="growth-fulltime-main"
SA_NAME="fulltime-ga4-reader"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID" >/dev/null
NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

echo "Turning on the four Google APIs this needs. They are free to use; if Google asks for billing, stop there."
gcloud services enable analyticsdata.googleapis.com iam.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com

if ! gcloud iam service-accounts describe "$SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="Full Time growth engine: Google Analytics reader (read-only)"
fi

if ! gcloud iam workload-identity-pools describe "$POOL" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL" --location=global \
    --display-name="GitHub Actions"
fi

if ! gcloud iam workload-identity-pools providers describe "$PROVIDER" \
    --location=global --workload-identity-pool="$POOL" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
    --location=global --workload-identity-pool="$POOL" \
    --display-name="growth-fulltime, main branch" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository == '${REPO}' && assertion.repository_owner_id == '${OWNER_ID}' && assertion.ref == 'refs/heads/main'"
fi

# Only this repository's workflows may act as the reader, and the reader has no
# Google Cloud role at all: its one permission is Viewer on the Analytics property.
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}" \
  >/dev/null

cat <<DONE

Done. Nothing secret was created.

1. In Google Analytics: Admin, Property access management, add
     ${SA}
   with the Viewer role.

2. In GitHub (github.com/${REPO}/settings/variables/actions), add three variables:
     GA4_WIF_PROVIDER     projects/${NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}
     GA4_SERVICE_ACCOUNT  ${SA}
     GA4_PROPERTY_ID      the numeric property ID (Admin, Property details), not the G- measurement ID

The next morning's control center loop reads Analytics on its own.
DONE
