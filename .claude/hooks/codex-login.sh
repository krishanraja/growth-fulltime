#!/usr/bin/env bash
# SessionStart: if Codex is not signed in, start the ChatGPT device sign-in and put the link and the
# one-time code in front of Krish, so no session stalls on Codex or asks him how to connect it
# (Krish, 2026-11-10: "ensure if codex is not connected, I am automatically given the link to sign
# in, instead of having you complain about it"; "i can just log in to a cloud session with codex
# sbscription - you give me the link and the code and I enter it when i click the link").
# His subscription, never an API key. Silent when Codex is already signed in. Never fails the session.
set -u
log="${TMPDIR:-/tmp}/codex-device-login.log"

if ! command -v codex >/dev/null 2>&1; then
  # A cloud container starts without Codex: install it there. Elsewhere (a machine without Codex) stay quiet.
  [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
  npm install -g @openai/codex >/dev/null 2>&1 || exit 0
  command -v codex >/dev/null 2>&1 || exit 0
fi

codex login status >/dev/null 2>&1 && exit 0

# Not signed in: start the device sign-in in the background (it waits up to 15 minutes for him) and read
# the link and code it prints.
rm -f "$log"
nohup codex login --device-auth >"$log" 2>&1 </dev/null &
url="" code=""
for _ in $(seq 1 50); do
  sleep 0.5
  [ -s "$log" ] || continue
  clean=$(sed 's/\x1b\[[0-9;]*m//g' "$log")
  url=$(printf '%s\n' "$clean" | grep -oE 'https://[^[:space:]]+/device[^[:space:]]*' | head -n1)
  code=$(printf '%s\n' "$clean" | grep -oE '\b[A-Z0-9]{4}-[A-Z0-9]{4,6}\b' | head -n1)
  [ -n "$url" ] && [ -n "$code" ] && break
done

if [ -n "$url" ] && [ -n "$code" ]; then
  msg="Codex sign-in: open $url and enter the code $code (sign in with your ChatGPT account; the code lasts 15 minutes)."
  ctx="Codex is not signed in on this machine. A device sign-in is already running in the background. Give Krish this link and code in your first reply, word for word, and nothing else about setup: $url and code $code. Do not ask for an API key and do not explain how to install or connect Codex. Before using Codex, check codex login status; once it says Logged in, carry on."
else
  msg="Codex is not signed in, and the device sign-in did not print a code (see $log)."
  ctx="Codex is not signed in and the automatic device sign-in did not produce a code (log: $log). Run codex login --device-auth yourself and give Krish the link and code it prints. Never ask for an API key."
fi
printf '{"systemMessage":"%s","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg" "$ctx"
exit 0
