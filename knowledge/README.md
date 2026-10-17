# Historical source material

This directory preserves the source playbook as planning history. It is not an
active job list, acquisition calendar or permission to use excluded channels.
The executable policy is in engine/policy.py; current instructions are AGENTS.md,
PLAYBOOK.md and EXECUTION-PLAN.md. Personal accounts, cold email and paid work
remain excluded even if historical source material recommends them.

The active schedule has two jobs in automations.json. The older handover and
source retain their historical conditions; do not recreate the eight-job setup.


Krish gave this engine its operating document on 16 October 2026, with the
brief to build "the dedicated growth engine for this app, obsessed with
getting this into market".

| File | What it is |
|---|---|
| `full-time-1000-users-playbook.md` | "Full Time: The 1,000 Free Users in 30 Days Playbook", as Krish gave it, with its numbered references. |

This is the source. **`PLAYBOOK.md` (repository root) is how this engine
runs it.** Each job in `jobs/` names the part it uses. When a job and the
document disagree, the job wins, because the playbook holds the document to
Full Time's canon, the rulings and Krish's rules.

## Where Full Time's canon and Krish's rules change the document

The document was written from the full-time repository on 16 October 2026.
Each change below is recorded so no session "fixes" it back:

1. **The rail comes first, as a gate in code.** The document's first move is
   "prove the rail fills before pushing anyone to it". The engine makes that
   a rule: `growth.py check` refuses any link that sends a fan to a match
   with fewer than 4 of the 6 AI Pundits. On 16 October every match on the
   rail had one.
2. **Decisions are gates, not assumptions.** The document recommends
   approving all seven of its decisions. Until Krish makes each one and
   full-time's decision log records it, the channel it governs is drafted
   but held (`rulings.json`). The engine's recommendations differ from the
   document's in timing on three: D1 takes effect when the rail gate opens;
   D2 waits for one weekend that fills the rail; D5 waits for D7 and for two
   weekends of an open gate.
3. **The cost per run.** The document budgets 2.14 US dollars per six-pundit
   run. full-time's `AGENTS.md` says "roughly $6" is right, and that 2.14 was
   measured on a cheaper judge bench. The engine quotes the canon's figure,
   with its source.
4. **Statistics stay in the document.** The market figures it cites (YouTube
   and Spotify shares, clip discovery, Robinhood's waitlist, NotebookLM's
   traffic, subreddit sizes, FPL registrations, ad prices) are planning
   context. None appears in public copy unless a job re-reads the source that
   day and cites it (AGENTS.md, rule 5).
5. **The beta tag is kept.** The document tags channels by name. Full Time's
   December bar counts testers by `utm_source=beta`
   (`docs/22-vision-and-beta.md`), so personal invites keep that tag and
   every other channel gets its own.
6. **UK English, and Full Time's words.** Copy follows full-time's
   `docs/01-brand.md`, `docs/07-marketing.md` and
   `docs/21-go-to-market-agent.md`. The document's sample lines are
   rechecked against them: "six AI pundits" becomes "six AI Pundits", and
   a post carries three emoji at most.
7. **Fixtures are re-read.** The document's calendar came from public
   fixture lists on 16 October. The Monday report re-reads each week's
   fixtures before any pack relies on them.
8. **The 17 October channel and cost limits narrow the active work.**
   `EXECUTION-PLAN.md` excludes Krish's personal social accounts, cold
   outbound email, paid creators and ads. It targets £0 new marketing cash
   using the product, brand accounts and explicit opt-ins. The source
   document's broader channel banks are historical options, including
   recommendations to use founder profiles or email press and creators.
