// TADSDI estimation.js: the estimation reference table embedded into
// interviewer prompt block 4 (DESIGN.md section 7). Lineage: System Design
// Primer powers-of-two and latency tables, Jeff Dean latency gists
// (jboner/2841832, hellerbarde/2843375). The interviewer grades claims
// against this table, not its own memory.

export const ESTIMATION_REFERENCE = `Back-of-the-envelope estimation reference.
The goal is order of magnitude: within 10x is success, within 2x is excellent.

Powers of two:
2^10 ~ 1 thousand (KB), 2^20 ~ 1 million (MB), 2^30 ~ 1 billion (GB),
2^40 ~ 1 trillion (TB), 2^50 ~ 1 quadrillion (PB).
Decimal: 1 KB = 10^3 B, 1 MB = 10^6, 1 GB = 10^9, 1 TB = 10^12, 1 PB = 10^15.
Useful: 86,400 s/day (~10^5), 2.5M s/month, 31.5M s/year (~3 x 10^7).

Latency numbers (Jeff Dean):
L1 cache ref 0.5 ns; mutex lock 25 ns; main memory ref 100 ns;
compress 1 KB (Snappy) 3 us; send 1 KB over 1 Gbps 10 us;
SSD random read 4 KB 150 us; memory sequential read 1 MB 250 us;
datacenter round trip 500 us; SSD sequential 1 MB 1 ms; HDD seek 10 ms;
HDD sequential 1 MB 20 ms; cross-continent packet CA->NL->CA ~150 ms.
Memory is ~100,000x faster than disk seek. SSD random read ~67x faster than HDD seek.

Latency requirement -> strategy:
< 1 ms: memory only. < 10 ms: SSD or local cache. < 100 ms: database or remote cache.
< 500 ms: 1-2 datacenter calls. < 1 s: multiple calls or one cross-region call.
> 1 s: async with a loading state.

Availability nines (downtime per year):
99% = 3.65 days; 99.9% = 8.77 h; 99.95% = 4.38 h; 99.99% = 52.6 min; 99.999% = 5.26 min.
Chained services multiply: 3 x 99.9% = 99.7%. Parallel redundancy: two 99% paths = 99.99%.

QPS: average QPS = DAU x actions per user / 86,400. Peak = average x 2-5.
Worked examples:
- Twitter-like: 300M DAU, 2 tweets/day -> write ~7K QPS, peak ~21K; 100 reads/day -> read ~350K QPS, peak ~1.05M; 50:1 read:write.
- URL shortener: 100M DAU, 0.1 creates/day -> write ~116 QPS; 5 redirects/day -> read ~5,800 QPS, peak ~29K.
- Chat: 50M DAU, 40 msgs/day -> ~23K QPS, peak ~115K.

Storage: daily = records/day x record size; yearly = daily x 365; total = yearly x retention years.
Examples: tweets ~400 B -> 600M/day = 240 GB/day, ~88 TB/yr. URL records ~300 B, 10M/day = 3 GB/day, ~11 TB over 10 years.

Bandwidth: incoming = write QPS x request size; outgoing = read QPS x response size.
Image hosting: 10K reads x 500 KB = 5 GB/s out -> CDN mandatory.

Server counts: web server ~1K-10K QPS; DB ~5K-10K simple QPS; Redis ~100K GET/SET QPS; queue node ~10K-100K msg/s.
servers = peak QPS / per-server QPS, x 2-3 for redundancy.

Common mistakes: forgetting peak multiplier, ignoring media storage, false precision (3,472 QPS -> say ~3.5K), forgetting replication x3, ignoring 30-50% metadata overhead, no growth headroom.`;
