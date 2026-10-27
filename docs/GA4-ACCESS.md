# Google Analytics access: one-time setup

Ruling (Krish, 2026-10-27): "Direct read-only API". The Measurement Analyst reads
Google Analytics 4 on fulltime.fm (measurement ID `G-W2QL8RKFJ1`, page views only)
through Google's Analytics Data API, with a read-only sign-in that Krish makes once.
The reader is `engine/ga4.py`. This page is the setup, in order.

## What it reads, and what it never is

- One aggregate report: new users, sessions and engaged sessions, by session
  source, medium, campaign and manual ad content. Manual ad content is the
  `utm_content` on the engine's links, which carries the creative ID.
- Counts only. It never asks for a user, client or device ID, and it cannot change
  anything in Google Analytics: the only permission it asks for is
  `analytics.readonly`.
- **These are web landings on fulltime.fm, never listeners.** A landing is someone
  opening the site. It never counts towards the North Star number, which is new
  listeners, and the engine keeps it apart from every listener number.
- **Consent item D7 is still open.** D7 covers PostHog and Google Analytics consent
  on fulltime.fm, with counsel's check. Reading aggregate reports does not close
  it, and nothing here changes what fulltime.fm collects or asks visitors. D7 must
  still close in the product before the first public post.

## Steps

You need about 15 minutes, on your own computer, signed in to the Google account
that owns the Full Time Google Analytics property.

### 1. Pick a Google Cloud project

Open [console.cloud.google.com](https://console.cloud.google.com). Create a project
(for example "Full Time growth") or pick an existing one of yours.

### 2. Turn on the Google Analytics Data API

In that project: APIs and services, Library, search for **Google Analytics Data
API**, then Enable.

### 3. Set up the sign-in screen

In Google Auth Platform (it may be called OAuth consent screen):

- Give the app a name, such as "Full Time growth engine", and your email.
- Audience: if the project belongs to a Google Workspace organisation, choose
  **Internal**. Otherwise choose **External** and add your own Google account as a
  test user.
- With External, set the publishing status to **In production**. An app left in
  Testing gets sign-ins that expire after seven days. Google then shows an
  "unverified app" screen the first time you sign in to your own app: choose
  Advanced, then continue. Nobody else uses this app, so it never needs Google's
  verification.

### 4. Create an OAuth client of type Desktop app

Clients (or Credentials), Create client, Application type **Desktop app**, any
name. Google shows a client ID and a client secret. Keep that window open for the
next step; do not paste either one into a chat, an issue, a pull request or a
commit.

### 5. Check your access in Google Analytics

In Google Analytics, Admin, Property access management, your own account needs at
least **Viewer** on the Full Time property. You already have it as the owner.

### 6. Find the numeric property ID

In Google Analytics, Admin, **Property details**. The property ID is a number
such as `123456789`. It is not the `G-W2QL8RKFJ1` measurement ID, which belongs to
the web stream. While you are there, check that the reporting time zone is
United Kingdom, so Google's days are London days. The report says so when they
are not.

### 7. Sign in once from your computer

From the repository folder:

```
python growth.py ga4 authorize --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
```

Add `--property-id YOUR_PROPERTY_ID` to save the number from step 6 as well. If
you leave `--client-secret` off, the command asks for it without showing it, which
keeps it out of your shell history. Your browser opens once. Sign in with the account from step 5 and allow
"See and download your Google Analytics data". The terminal then says it is signed
in.

It writes `local/ga4/oauth.json`, which only you can read where the system allows
it (mode 600). `local/` is never committed. The file holds the client ID, the
client secret, a refresh token and the property ID. If you left the property ID
off, fill `property_id` in that file with the number from step 6.

### 8. Check it

```
python growth.py ga4 doctor
```

It says where the credentials came from, whether the property ID is set and
whether a token refresh works. It never prints a secret. Then try a week:

```
python growth.py ga4 report --days 7 --out local/ga4/week.json
```

It covers the seven complete London days ending yesterday, writes the export
under `local/` only, and prints the counts and the path.

### 9. Give the cloud sessions the same access

Open the cloud environment's settings (the cloud environment menu in the session's
title bar, then Edit). Add four secrets, under Network secrets where that section
is offered, otherwise as environment variables:

| Name | Value |
|---|---|
| `GA4_CLIENT_ID` | `client_id` from `local/ga4/oauth.json` |
| `GA4_CLIENT_SECRET` | `client_secret` from that file |
| `GA4_REFRESH_TOKEN` | `refresh_token` from that file |
| `GA4_PROPERTY_ID` | the number from step 6 |

Copy each value from the file yourself. Never paste them into a chat. A new
session picks them up. If the environment limits network access, allow
`oauth2.googleapis.com` and `analyticsdata.googleapis.com` under Allowed domains.

When those four are set, the reader uses them and ignores the file.

## If something goes wrong

The commands answer with a code and a plain sentence, never a secret.

| Code | What to do |
|---|---|
| `missing_ga4_credentials` | Do step 7, or step 9 in the cloud |
| `missing_ga4_property_id`, `ga4_property_id_invalid` | Use the number from step 6, not the `G-` ID |
| `ga4_credentials_exposed` | Run `chmod 600 local/ga4/oauth.json` |
| `unauthorized` | The sign-in was revoked or expired (see step 3 about Testing): run step 7 again and update step 9 |
| `forbidden` | Check step 2 and step 5 |
| `ga4_unavailable` | Google did not answer; try later |

To stop the engine reading Google Analytics, remove the app at
[myaccount.google.com/permissions](https://myaccount.google.com/permissions), or
delete the OAuth client from step 4, then remove the four secrets.
