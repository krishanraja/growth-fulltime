# Google Analytics access

Ruling (Krish, 2026-10-27): "just get google analytics data from control center,
much easier". The Measurement Analyst reads Google Analytics 4 landings on fulltime.fm
(measurement ID `G-W2QL8RKFJ1`, page views only) **from Control Center**. Krish has
nothing to set up. Control Center holds the Google sign-in on its own server, as it
does for its other keys, and hands the engine the week's landings in its daily
directive (`ga4_landings`). The engine reads that today (`engine/control_center.py`,
`measurement_lines`); until Control Center sends it, each report says no landings came.

**Status, read live on 27 October:** Control Center cannot do this yet. Its gateway has
no Google Analytics operation, and the only Analytics fact it holds for Full Time is
that the tag is on the site. The build is briefed exactly in
[`briefs/2026-10-27-control-center-measurement.md`](../briefs/2026-10-27-control-center-measurement.md),
section 1, for a Control Center session.

The two direct routes below stay in the repository as fallbacks. Neither runs unless
someone switches it on, and neither is on Krish's list.

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

## Fallback routes, not in use

**Route A, GitHub Actions, keyless.** The daily control center loop
already runs in GitHub Actions. It proves who it is to Google with GitHub's own
short-lived identity token, and Google answers with a ten-minute token that can only
read Analytics. No key, client secret or refresh token exists anywhere, so there is
nothing to leak, rotate or let expire, and nothing depends on a chat session or on
your computer being on. Google accepts the identity only from
`krishanraja/growth-fulltime` on its `main` branch (checked against your numeric
GitHub ID), and the reader it acts as has one permission: Viewer on the Full Time
property. The export stays on the runner and is never uploaded.

**Route B, your own computer (optional).** A one-time sign-in that saves a refresh
token in `local/ga4/oauth.json`, for running reports by hand on your machine.

Why not Vercel: Vercel's settings serve the product's own runtime. Reading Analytics
there would mean building and guarding a new endpoint on fulltime.fm just to hand the
numbers back to this engine.

## Route A: GitHub Actions, keyless (about 10 minutes, once)

1. Open [Google Cloud Shell](https://shell.cloud.google.com), signed in to the Google
   account that owns the Full Time Google Analytics property. Pick or create a
   project (for example "Full Time growth") and note its project ID.
2. Upload or paste [`scripts/ga4-github-setup.sh`](../scripts/ga4-github-setup.sh),
   then run `bash ga4-github-setup.sh YOUR_PROJECT_ID`. It turns on four free Google
   APIs, creates the read-only reader and the GitHub trust, and prints what to do
   next. Running it twice changes nothing.
3. In Google Analytics: Admin, **Property access management**, add the reader's
   email the script printed, with the **Viewer** role and nothing more.
4. In GitHub: this repository, Settings, Secrets and variables, Actions,
   **Variables** (not secrets), add the three the script printed:
   `GA4_WIF_PROVIDER`, `GA4_SERVICE_ACCOUNT` and `GA4_PROPERTY_ID` (the number from
   Admin, Property details, not the `G-` ID).
5. Check it: Actions, **control center loop**, Run workflow on `main`. The "Read
   Google Analytics landings" step prints only whether the read worked, or its
   error code: this repository is public, so its run logs are too, and counts never
   go there. From then on every morning's loop reads it on its own. It starts once
   this work is merged into `main`, because the morning loop runs from `main`.

To stop it, delete the three variables, or remove the reader from Property access
management. Either takes effect at the next run.

## Route B: sign in from your own computer (optional)

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

## If something goes wrong

The commands answer with a code and a plain sentence, never a secret.

| Code | What to do |
|---|---|
| `missing_ga4_credentials` | Route A: check the three variables. Route B: do step 7 |
| `missing_ga4_property_id`, `ga4_property_id_invalid` | Use the number from step 6, not the `G-` ID |
| `ga4_credentials_exposed` | Run `chmod 600 local/ga4/oauth.json` |
| `unauthorized` | Route A: check the reader is still a Viewer on the property. Route B: the sign-in was revoked or expired (see step 3 about Testing); run step 7 again |
| `forbidden` | Check step 2 and step 5 |
| `ga4_unavailable` | Google did not answer; try later |

To stop route B, remove the app at
[myaccount.google.com/permissions](https://myaccount.google.com/permissions), or
delete the OAuth client from step 4.
