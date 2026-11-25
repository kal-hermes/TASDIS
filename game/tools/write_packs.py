"""Build the seven remaining prep packs and embed them into the bank.

Mirrors plans/prep-pack-url-shortener.json: gist, five dimensions keyed
1-5, one anchor per hidden guidance item keyed 1-6, at least six probes
with step 1-5 and speakable text. Numbers were computed, not guessed.
"""
import json

PACKS = {
    "rate-limiter": {
        "gist": "A counting service that stands in front of a public API. "
                "Ten million requests per second at peak, and every request "
                "pays a five millisecond tax. The hard part is not counting: "
                "it is counting fast, at the edge, with rules that change "
                "every thirty seconds.",
        "dimensions": {
            "1": [
                "Peak fleet traffic about 10 million requests per second",
                "Limits are per API key and per endpoint, for example 1000 "
                "requests per minute",
                "The limiter adds under 5 ms at p99",
                "Small overshoot is fine but a client never exceeds 110 "
                "percent of its limit",
                "A strong candidate asks for scale, latency, and the "
                "overshoot policy instead of inventing them.",
            ],
            "2": [
                "The limiter sits inline on the request path, closest to the "
                "API edge",
                "The decision store is a fast in-memory counter, not a "
                "database round trip per request",
                "Sketch the request path: key, endpoint, decision, then the "
                "real backend",
                "A strong candidate draws the inline position and names the "
                "counter store before picking algorithms.",
            ],
            "3": [
                "Counters per key and endpoint: fixed window, sliding "
                "window, or token bucket",
                "Token bucket absorbs bursts: 1000 per minute fills at "
                "about 17 per second",
                "The 110 percent ceiling sizes the burst capacity of the "
                "bucket",
                "Counting survives node restarts without resetting every "
                "client's budget",
                "A strong candidate compares window algorithms against the "
                "overshoot tolerance.",
            ],
            "4": [
                "10 million decisions per second is the bottleneck, not the "
                "protected API",
                "A central store takes a network round trip per request, so "
                "the decision lives at the edge node",
                "Local counters with short sync windows trade a little "
                "overshoot for latency",
                "Rule changes reach every node within 30 seconds, a push "
                "not a poll",
                "A strong candidate measures the decision path in "
                "microseconds and syncs asynchronously.",
            ],
            "5": [
                "429 responses carry Retry-After and the remaining quota "
                "headers",
                "Clients read quota headers instead of probing until "
                "rejection",
                "Rule service, rollout, and rollback fit the 30 second "
                "budget",
                "A strong candidate treats the response contract as part of "
                "the product.",
            ],
        },
        "anchors": {
            "1": "Hearing the fleet scale: the candidate states ten million "
                 "requests per second at peak and asks where the limiter runs",
            "2": "Hearing the dimension: the candidate counts per key and "
                 "per endpoint, not one global bucket",
            "3": "Hearing the tax: the candidate budgets under five "
                 "milliseconds at p99 for the decision",
            "4": "Hearing the overshoot: the candidate accepts a small "
                 "burst but holds a hard ceiling at 110 percent",
            "5": "Hearing the contract: the candidate returns 429 with "
                 "Retry-After and quota headers, and says clients should "
                 "read them",
            "6": "Hearing the rollout: the candidate pushes rule changes "
                 "fleet wide inside thirty seconds",
        },
        "probes": [
            {"step": 1, "q": "A client hits exactly its limit. How much "
                             "over can it go before you hard reject?"},
            {"step": 2, "q": "Where does the decision live: at the edge "
                             "node, or in a central store? What does the "
                             "central store cost per request?"},
            {"step": 3, "q": "Fixed window, sliding window, or token "
                             "bucket: which one absorbs a client that "
                             "bursts 500 requests in two seconds?"},
            {"step": 4, "q": "You picked local counters for speed. The "
                             "platform team changes a limit right now. "
                             "When does every node enforce it?"},
            {"step": 4, "q": "Your store takes two milliseconds per "
                             "lookup at ten million requests per second. "
                             "Walk me through the request path."},
            {"step": 5, "q": "The client got a 429. What exactly is in "
                             "the response, and what should it do with "
                             "it?"},
        ],
    },
    "news-feed": {
        "gist": "A read-mostly timeline service. Fifty million daily users "
                "each follow about two hundred accounts, so every post "
                "multiplies into two hundred deliveries. The design question "
                "is where that multiplication happens: at write time into "
                "per-user feeds, or at read time from the author's timeline.",
        "dimensions": {
            "1": [
                "About 50 million daily users, each following about 200 "
                "accounts",
                "Reads outnumber writes about 100 to 1",
                "The first feed page loads in under 200 ms at p95",
                "A post lands in follower feeds within a few seconds, so "
                "strict global order is not required",
                "A strong candidate asks for user counts, follow graph "
                "shape, and freshness tolerance instead of inventing them.",
            ],
            "2": [
                "Two candidate shapes: fan out on write into per-user "
                "feeds, or merge on read from followed authors",
                "The read to write ratio of about 100 to 1 argues for "
                "precomputed feeds",
                "Sketch the write path: post, fan-out, feed store; and the "
                "read path: user, feed page",
                "A strong candidate names both shapes and picks one from "
                "the ratio.",
            ],
            "3": [
                "The per-user feed store keeps the newest 1000 posts, a "
                "fixed window with cheap eviction",
                "Feed entries hold post references, not copies of media",
                "Storage lands near 50 billion feed entries across users",
                "Paging by post id or rank keeps the 200 ms page inside "
                "the store's happy path",
                "A strong candidate sizes the feed store and keeps media "
                "out of it.",
            ],
            "4": [
                "Fan-out is the bottleneck: about 100 million posts per day "
                "times 200 followers lands near 231 thousand feed inserts "
                "per second",
                "Celebrity accounts with millions of followers cannot fan "
                "out synchronously, so the hybrid splits normal writes from "
                "huge ones",
                "Huge accounts merge at read time from the author timeline; "
                "normal accounts precompute",
                "A queue absorbs the fan-out burst; a few seconds of delay "
                "is inside the requirement",
                "A strong candidate spots the celebrity problem without "
                "being told.",
            ],
            "5": [
                "Every post carries images and short video, so the feed "
                "serves references to an object store and CDN",
                "The first page weights recent, engageable posts, not "
                "strict newest",
                "Ordering within a few seconds is fine; services need no "
                "global clock",
                "A strong candidate moves bytes to the CDN and keeps the "
                "feed index small.",
            ],
        },
        "anchors": {
            "1": "Hearing the graph: the candidate states 50 million users "
                 "and about 200 follows each, and connects follows to "
                 "fan-out cost",
            "2": "Hearing the imbalance: the candidate states reads "
                 "outnumber writes about 100 to 1 and lets it pick "
                 "precomputed feeds",
            "3": "Hearing the budget: the candidate targets under 200 ms "
                 "at p95 for the first page",
            "4": "Hearing the freshness: the candidate accepts seconds of "
                 "delay and drops strict ordering as a requirement",
            "5": "Hearing the window: the candidate stores the newest 1000 "
                 "posts per user with cheap eviction",
            "6": "Hearing the media: the candidate plans object storage "
                 "and CDN references for images and short video",
        },
        "probes": [
            {"step": 1, "q": "A user follows a celebrity with 50 million "
                             "followers. What happens when that celebrity "
                             "posts?"},
            {"step": 2, "q": "Fan out on write or merge on read: what does "
                             "the 100 to 1 ratio tell you to pick?"},
            {"step": 3, "q": "The feed page must render in 200 "
                             "milliseconds. Where do the images and the "
                             "short video come from?"},
            {"step": 4, "q": "Your fan-out queue is 30 seconds behind "
                             "during a live sports event. What does the "
                             "user see, and is that acceptable?"},
            {"step": 4, "q": "Storage keeps the newest 1000 posts per "
                             "user. A user scrolls past post 1000. What "
                             "happens?"},
            {"step": 5, "q": "Two posts arrive three seconds apart from "
                             "two different authors. Does the feed promise "
                             "an order between them?"},
        ],
    },
    "chat": {
        "gist": "A delivery system wearing a messaging costume. Fifty "
                "billion messages per day is about 579 thousand per second, "
                "and the hard requirements are order and no loss inside one "
                "conversation. Connections, queues, and receipts all serve "
                "that one promise.",
        "dimensions": {
            "1": [
                "About 500 million daily users sending 50 billion messages "
                "per day, about 579 thousand per second",
                "One to one chats and group chats up to 500 members",
                "Under 500 ms at p95 from send to delivery when both sides "
                "are online",
                "A strong candidate asks for scale, group shape, and the "
                "online delivery budget instead of inventing them.",
            ],
            "2": [
                "Persistent connections carry the realtime path; a message "
                "lands on a gateway, then routes to recipient connections",
                "Group fan-out copies into per-conversation recipient "
                "queues, up to 500 recipients",
                "Sketch the path: sender, gateway, router, recipient "
                "gateway, connection",
                "A strong candidate draws the connection layer before the "
                "storage layer.",
            ],
            "3": [
                "Per-conversation ordering: sequence numbers assigned once, "
                "at one place",
                "No loss: the sender retries until an ack, and the store "
                "acks before fan-out completes",
                "The message store is keyed by conversation and appended "
                "in order",
                "A strong candidate puts the order guarantee in one "
                "component and proves no-loss with the ack chain.",
            ],
            "4": [
                "The connection layer is the bottleneck: millions of live "
                "connections per gateway box, idle traffic included",
                "Gateways and routers scale horizontally; routing needs "
                "only the recipient's current gateway",
                "Offline recipients leave the realtime path: a push wakes "
                "them within 60 seconds, then a sync pulls missed messages "
                "on reconnect",
                "A strong candidate separates the online path from the "
                "offline catch-up path.",
            ],
            "5": [
                "Read receipts and typing indicators ride the same "
                "connections as lightweight events, not as messages",
                "Receipts are best effort, messages are guaranteed; the "
                "two promises differ",
                "Multi-device sync reads from the per-conversation store, "
                "not from push",
                "A strong candidate separates guaranteed messages from "
                "lightweight signals.",
            ],
        },
        "anchors": {
            "1": "Hearing the scale: the candidate states 50 billion "
                 "messages per day, about 579 thousand per second",
            "2": "Hearing the shapes: the candidate supports one to one "
                 "chats and groups up to 500 members",
            "3": "Hearing the budget: the candidate targets under 500 ms "
                 "at p95 for online delivery",
            "4": "Hearing the order: the candidate assigns sequence inside "
                 "one conversation and never loses a message",
            "5": "Hearing the offline path: the candidate pushes within 60 "
                 "seconds and syncs missed messages on reconnect",
            "6": "Hearing the signals: the candidate carries read receipts "
                 "and typing as lightweight events, distinct from messages",
        },
        "probes": [
            {"step": 1, "q": "A group has 500 members and one member is "
                             "offline. What must still happen for the "
                             "other 499?"},
            {"step": 2, "q": "Walk me through the life of one message from "
                             "send tap to the recipient's screen."},
            {"step": 3, "q": "Two messages leave the sender in order but "
                             "take different routes. What keeps their "
                             "arrival order?"},
            {"step": 4, "q": "Your gateway holds 2 million connections. "
                             "It crashes. What does the user see, and what "
                             "happens to in-flight messages?"},
            {"step": 4, "q": "The recipient is offline for six hours with "
                             "bad mobile signal. How do the messages reach "
                             "them?"},
            {"step": 5, "q": "A typing indicator drops on a congested "
                             "network. Does anything break? What if a "
                             "message drops instead?"},
        ],
    },
    "autocomplete": {
        "gist": "A top-ten service on a firehose. Eight billion searches a "
                "day times ten keystroke requests is about 926 thousand "
                "requests per second, and every answer is the same shape: "
                "the top ten completions of a prefix. The design is one "
                "small, hot, hourly-refreshed index served from memory.",
        "dimensions": {
            "1": [
                "About 8 billion searches per day, about 10 keystroke "
                "requests per search, so about 926 thousand requests per "
                "second",
                "Answers land in under 100 ms at p99",
                "Only the top 10 suggestions per prefix matter",
                "A strong candidate multiplies searches by keystrokes and "
                "asks for the latency budget instead of inventing them.",
            ],
            "2": [
                "A prefix service answers from memory, not from the search "
                "backend",
                "The request is tiny and cache friendly at the edge",
                "Sketch the path: keystroke, edge, prefix index, top 10 "
                "back",
                "A strong candidate keeps the search index out of the "
                "keystroke path.",
            ],
            "3": [
                "The index covers about 100 million distinct queries, "
                "ranked by frequency over the last 24 hours",
                "Trie or precomputed top-10 per prefix; only hot prefixes "
                "need their own list",
                "Top 10 is small enough to ship as one cached payload per "
                "prefix",
                "A strong candidate picks a structure where the answer is "
                "precomputed, not computed per keystroke.",
            ],
            "4": [
                "About 926 thousand requests per second is the bottleneck; "
                "the index lives in memory, replicated near users",
                "The trend refresh runs hourly: a batch job rebuilds ranks "
                "from the last 24 hours, then swaps",
                "A stale index for minutes is fine; recomputing per "
                "request is not",
                "The 2 percent banned list filters at index build and "
                "again at serve",
                "A strong candidate separates the per-hour build from the "
                "per-keystroke serve.",
            ],
            "5": [
                "The hourly rank swap bounds staleness without touching "
                "the hot path",
                "Prefix caching at the edge absorbs repeat keystroke "
                "storms",
                "Banned terms drop before they reach the suggestion list, "
                "at build and at serve",
                "A strong candidate talks about swap atomicity so no "
                "request sees a half-built index.",
            ],
        },
        "anchors": {
            "1": "Hearing the multiplier: the candidate states about 926 "
                 "thousand keystroke requests per second",
            "2": "Hearing the budget: the candidate targets under 100 ms "
                 "at p99",
            "3": "Hearing the shape: the candidate serves a precomputed "
                 "top 10 per prefix",
            "4": "Hearing the trend: the candidate rebuilds ranks from the "
                 "last 24 hours and swaps hourly",
            "5": "Hearing the index size: the candidate plans for about "
                 "100 million distinct queries in memory",
            "6": "Hearing the filter: the candidate drops the 2 percent "
                 "banned queries at build time and at serve time",
        },
        "probes": [
            {"step": 1, "q": "The user typed three letters. Where does the "
                             "answer come from, and what does it cost?"},
            {"step": 2, "q": "Your p99 is 120 milliseconds. What are the "
                             "first two places the time goes?"},
            {"step": 3, "q": "One hundred million distinct queries. Do you "
                             "precompute the top ten for every possible "
                             "prefix? Why or why not?"},
            {"step": 4, "q": "A term goes viral right now. When does it "
                             "appear in suggestions, and what had to run?"},
            {"step": 4, "q": "The rank swap happens while requests arrive. "
                             "What does a request see mid-swap?"},
            {"step": 5, "q": "A banned term sneaks into the index "
                             "overnight. When does it disappear from "
                             "suggestions?"},
        ],
    },
    "web-crawler": {
        "gist": "A polite queue with a dedup problem. About 400 pages per "
                "second on average, and every host allows only one request "
                "per second, so the crawler is mostly a scheduler. The "
                "other half is noticing that about a third of what it "
                "fetched, it already had.",
        "dimensions": {
            "1": [
                "About 1 billion pages per month, about 400 pages per "
                "second on average",
                "Politeness caps one request per second per host",
                "Popular pages re-crawl every 24 hours, the rest every 30 "
                "days",
                "A strong candidate converts the monthly budget into a "
                "rate and asks about politeness rules instead of inventing "
                "them.",
            ],
            "2": [
                "A frontier of URLs with priority and schedule, workers "
                "that fetch, and a store that keeps pages",
                "The scheduler holds per-host queues so politeness is per "
                "host, not per worker",
                "Sketch the loop: pull from frontier, check robots, fetch, "
                "extract links, push new URLs",
                "A strong candidate draws the frontier as the heart of the "
                "system.",
            ],
            "3": [
                "robots.txt fetched and cached per host, obeyed for every "
                "request",
                "A URL seen-set and content hashes dedupe pages before "
                "storage",
                "The page store records fetch time per URL, so schedules "
                "re-crawl on their own clocks",
                "A strong candidate caches robots per host and records "
                "what was allowed.",
            ],
            "4": [
                "The politeness ceiling is the bottleneck: 400 pages per "
                "second needs at least 386 hosts in flight",
                "Slow or large hosts stall a worker; per-host queues stop "
                "one bad host from blocking the fleet",
                "About 30 percent of fetches are near-duplicates, so dedup "
                "runs before parsing and storage, not after",
                "A strong candidate sizes the seen-set and the hash store "
                "for billions of URLs.",
            ],
            "5": [
                "The frontier persists: a worker crash loses no queued "
                "URL, so the queue is durable or journaled",
                "Re-crawl schedules ride the page record: fetched at, next "
                "fetch at",
                "Rate limits and retries per host keep the crawl inside "
                "each site's terms",
                "A strong candidate treats crash recovery as a first "
                "class requirement, not an afterthought.",
            ],
        },
        "anchors": {
            "1": "Hearing the rate: the candidate converts 1 billion pages "
                 "per month into about 400 pages per second",
            "2": "Hearing the politeness: the candidate caps one request "
                 "per second per host and builds per-host queues",
            "3": "Hearing the schedule: the candidate re-crawls popular "
                 "pages every 24 hours and the rest every 30 days",
            "4": "Hearing the rules: the candidate fetches and obeys "
                 "robots.txt per host and keeps site terms",
            "5": "Hearing the duplicates: the candidate expects about 30 "
                 "percent near-duplicates and dedupes by content hash",
            "6": "Hearing the durability: the candidate guarantees a "
                 "crashed worker loses no queued URL",
        },
        "probes": [
            {"step": 1, "q": "Politeness allows one request per second per "
                             "host. What does that imply about how many "
                             "hosts you must crawl in parallel?"},
            {"step": 2, "q": "Walk me through one URL's life from "
                             "discovery to stored page."},
            {"step": 3, "q": "A site forbids crawling two of its ten "
                             "sections. Where is that enforced, and where "
                             "is it remembered?"},
            {"step": 4, "q": "One host serves one page every eight seconds "
                             "under load. What does your crawler do to it, "
                             "and to itself?"},
            {"step": 4, "q": "About 30 percent of fetches turn out to be "
                             "duplicates. Where in the pipeline do you "
                             "catch them, and what do you skip?"},
            {"step": 5, "q": "A worker dies holding 50 queued URLs in "
                             "memory. Show me what gets lost, if anything."},
        ],
    },
    "unique-id-generator": {
        "gist": "A 64-bit counter that never collides across data centers. "
                "Ten million IDs per second, roughly time ordered, answered "
                "locally in under a millisecond with no network round trip. "
                "The whole design is a bit budget: how to split 64 bits "
                "between time, machine, and sequence.",
        "dimensions": {
            "1": [
                "About 10 million IDs per second at peak across all "
                "services",
                "IDs are unique across data centers and never reused",
                "IDs are roughly time ordered so a one hour range scan "
                "reads few pages",
                "A strong candidate asks for rate, ordering strength, and "
                "the bit budget instead of inventing them.",
            ],
            "2": [
                "Two shapes: a central issuing service, or local "
                "generation from a machine id plus time",
                "A central service needs a network round trip per ID; the "
                "requirement forbids that",
                "Sketch the local shape: machine id assigned once, "
                "timestamp and sequence fill the rest",
                "A strong candidate rejects the central issuer on the "
                "round trip requirement alone.",
            ],
            "3": [
                "64 bits split like: 41 bits of milliseconds, 10 bits of "
                "machine, 12 bits of sequence",
                "41 bits of milliseconds covers about 70 years; 12 bits of "
                "sequence gives 4096 IDs per millisecond per machine, "
                "about 4 million per second",
                "Three machines cover the 10 million per second peak; 1024 "
                "machine ids give huge headroom",
                "Rough ordering falls out of the timestamp bits; only IDs "
                "within one millisecond on one machine need the sequence",
                "A strong candidate does the bit arithmetic out loud and "
                "checks the peak against it.",
            ],
            "4": [
                "The bottleneck is the bit budget, not throughput: 4096 "
                "IDs per millisecond per machine bounds burst on one node",
                "Burst beyond 4096 per millisecond spills to another "
                "machine or waits for the next millisecond",
                "Machine id assignment happens once at boot through "
                "coordination, not per ID",
                "A local call answers in under 1 ms because no network "
                "ride sits in the path",
                "A strong candidate knows the sequence limit and where "
                "overflow goes.",
            ],
            "5": [
                "A clock that steps back up to 5 seconds must not reuse "
                "sequence space: wait out the drift or bump a generation",
                "Time ordering survives data center boundaries because "
                "timestamps compare across sites",
                "Range scans on a one hour window read a narrow time band "
                "of the index",
                "A strong candidate explains what breaks if the clock "
                "lies, and bounds it.",
            ],
        },
        "anchors": {
            "1": "Hearing the rate: the candidate states 10 million IDs "
                 "per second at peak",
            "2": "Hearing the uniqueness domain: the candidate guarantees "
                 "uniqueness across data centers with no reuse ever",
            "3": "Hearing the order: the candidate makes IDs roughly time "
                 "ordered so one hour scans read few pages",
            "4": "Hearing the locality: the candidate generates locally "
                 "with no network round trip per ID, under 1 ms",
            "5": "Hearing the budget: the candidate fits every ID in 64 "
                 "bits and splits time, machine, and sequence",
            "6": "Hearing the clock: the candidate tolerates a 5 second "
                 "backward step without reusing IDs",
        },
        "probes": [
            {"step": 1, "q": "IDs must never be reused. What does 'never' "
                             "cost you when a machine restarts "
                             "mid-millisecond?"},
            {"step": 2, "q": "Why not a database that hands out IDs? What "
                             "does the requirement forbid?"},
            {"step": 3, "q": "Split 64 bits your way. How many years does "
                             "your timestamp last, and how many IDs per "
                             "second can one machine emit?"},
            {"step": 4, "q": "One machine gets a burst of 10 thousand ID "
                             "requests in one millisecond. What exactly "
                             "happens?"},
            {"step": 4, "q": "The clock on one node jumps back 5 seconds. "
                             "Walk me through the IDs it emits next."},
            {"step": 5, "q": "Your service stores IDs in a database index. "
                             "Why does rough time order matter for a one "
                             "hour range scan?"},
        ],
    },
    "notification-system": {
        "gist": "A delivery pipeline that fans one event out to phones, "
                "inboxes, and SMS gateways, with a per-person rulebook. "
                "About 2,315 notifications per second on average and 20 "
                "thousand at peak, and the guarantees are timing, "
                "preferences, and never the same notification twice.",
        "dimensions": {
            "1": [
                "About 200 million notifications per day, about 2,315 per "
                "second on average with a peak of 20 thousand per second",
                "Channels: mobile push through APNs and FCM, plus email "
                "and SMS",
                "Dispatch to the provider starts within 5 seconds of the "
                "event at p95",
                "A strong candidate asks for volume, channel mix, and the "
                "dispatch budget instead of inventing them.",
            ],
            "2": [
                "An event bus receives triggers; a fan-out layer resolves "
                "audience and channels; provider adapters send",
                "Each channel has its own adapter and rate limits: APNs, "
                "FCM, email, SMS",
                "Sketch the path: event, dedupe, preference check, channel "
                "queue, provider",
                "A strong candidate keeps channel specifics inside "
                "adapters.",
            ],
            "3": [
                "The 5 second budget makes the event to dispatch path "
                "short: a queue, a preference lookup, a provider call",
                "Preferences and quiet hours are one keyed lookup per "
                "user, cached",
                "Bulk campaigns and single events share the path but ride "
                "separate queues so a campaign cannot delay a single event",
                "A strong candidate isolates campaign bursts from single "
                "events.",
            ],
            "4": [
                "Provider rate limits are the bottleneck, not the internal "
                "bus: 20 thousand per second must spread across provider "
                "quotas",
                "Retries up to 5 with exponential backoff stretch delivery "
                "over about 31 seconds before a dead letter queue",
                "The dedupe window: one event never notifies one user "
                "twice inside 24 hours, keyed by user plus event",
                "A strong candidate treats provider quotas as capacity and "
                "the dedupe key as a correctness feature.",
            ],
            "5": [
                "Per channel and per category preferences plus quiet hours "
                "gate every send",
                "The dead letter queue captures exhausted sends for "
                "inspection and replay",
                "Delivery receipts and provider feedback close the loop "
                "per notification",
                "A strong candidate makes preferences enforceable at "
                "dispatch time, not just at compose time.",
            ],
        },
        "anchors": {
            "1": "Hearing the volume: the candidate states about 200 "
                 "million per day with a 20 thousand per second peak",
            "2": "Hearing the channels: the candidate names mobile push "
                 "through APNs and FCM, email, and SMS",
            "3": "Hearing the budget: the candidate dispatches to "
                 "providers within 5 seconds at p95",
            "4": "Hearing the rulebook: the candidate applies per channel "
                 "and per category preferences with quiet hours",
            "5": "Hearing the retry: the candidate retries up to 5 times "
                 "with backoff, then dead letters",
            "6": "Hearing the dedupe: the candidate blocks repeat "
                 "notifications for one user and one event inside 24 hours",
        },
        "probes": [
            {"step": 1, "q": "A campaign targets 80 million users at noon. "
                             "What does your peak look like, and what "
                             "absorbs it?"},
            {"step": 2, "q": "One event must reach a user's phone, inbox, "
                             "and SMS. Walk me through what happens and "
                             "where it can fan out."},
            {"step": 3, "q": "Dispatch must start within 5 seconds. What "
                             "sits between the event and the provider "
                             "call?"},
            {"step": 4, "q": "It is 2 AM for the user and a marketing "
                             "event fires. Who decides that nothing is "
                             "sent, and when?"},
            {"step": 4, "q": "FCM rejects a batch because of a rate limit. "
                             "What happens to those notifications over the "
                             "next minute?"},
            {"step": 5, "q": "A payment event retried and the user got two "
                             "alerts. What key would have stopped that?"},
        ],
    },
}

SLUGS = ["rate-limiter", "news-feed", "chat", "autocomplete",
         "web-crawler", "unique-id-generator", "notification-system"]

for slug in SLUGS:
    pack = PACKS[slug]
    assert len(pack["dimensions"]) == 5
    assert len(pack["anchors"]) == 6
    assert len(pack["probes"]) >= 6
    assert all(1 <= p["step"] <= 5 and p["q"].strip() for p in pack["probes"])
    # anchor count must match the problem's hidden_guidance count
    problem_path = f"js/problems/{slug}.json"
    problem = json.load(open(problem_path))
    assert len(problem["hidden_guidance"]) == len(pack["anchors"]), slug
    with open(f"../plans/prep-pack-{slug}.json", "w") as f:
        json.dump(pack, f, indent=2, ensure_ascii=False)
        f.write("\n")
    problem["interviewer_brief"] = pack
    with open(problem_path, "w") as f:
        json.dump(problem, f, indent=2, ensure_ascii=False)
        f.write("\n")
    # read back: embedded pack survives a JSON round trip
    back = json.load(open(problem_path))
    assert back["interviewer_brief"]["gist"] == pack["gist"]
    print(f"{slug}: draft written, embedded, verified ({len(pack['probes'])} probes)")

print("all 7 packs done")
