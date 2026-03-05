<!-- Last generated: 2026-03-05T02:15:24Z -->

# Team Deakins — Transcription Progress

_Generated: 2026-03-05T02:15:24Z_

## Summary

| Metric | Count |
|--------|-------|
| Total episodes with audio | 344 |
| Diarized (speakers detected) | 11 |
| Transcribed (no speakers) | 8 |
| Pending | 325 |

### Overall completion

```
[##--------------------------------------] 6%  (19/344)
```

## Most Recent Completed Runs (last 10)

| Episode | Run ID | Speakers | Processing Time |
|---------|--------|----------|----------------|
| S00E004__2020-04-28__practical-lighting__libsyn_c615bbc2d7 | `run_20260305015618__larg__dz` | 2 | 302s |
| S02E175__2026-01-07__embeth-davidtz-actor-director__libsyn_cbe317a723 | `run_20260304220257__larg__dz` | 4 | 647s |
| S02E174__2025-12-31__césar-charlone-cinematographer__libsyn_4584a2f268 | `run_20260304220257__larg__dz` | 4 | 615s |
| S02E173__2025-12-24__kate-winslet-actor-director__libsyn_38ac05e287 | `run_20260304220257__larg__dz` | 4 | 834s |
| S02E172__2025-12-17__kleber-mendonça-filho-writer-director__libsyn_1dd9b3f88b | `run_20260304220257__larg__dz` | 3 | 572s |
| S02E171__2025-12-10__leds-with-jeffrey-lee-phd__libsyn_2d1ea870c4 | `run_20260304220257__larg__dz` | 3 | 614s |
| S02E169__2025-11-26__edgar-wright-director__libsyn_f6853474de | `run_20260304220257__larg__dz` | 3 | 821s |
| S02E168__2025-11-19__ted-schilowitz-futurist__libsyn_256be46110 | `run_20260304220257__larg__dz` | 3 | 608s |
| S02E167__2025-11-12__james-laxton-cinematographer__libsyn_1b17cab677 | `run_20260304220257__larg__dz` | 3 | 651s |
| S02E164__2025-10-22__28-years-later-with-anthony-dod-mantle__libsyn_6ba11a9300 | `run_20260304220257__larg__dz` | 3 | 784s |

## Pending Episodes (first 10)

| Episode | Audio Size |
|---------|-----------|
| S00E005__2020-04-30__composition__libsyn_e4602315ec | 74.2 MB |
| S00E006__2020-05-03__bev-wood-journey-from-film-to-digital__libsyn_fd4f961326 | 117.2 MB |
| S00E006__2020-05-06__lens-choice__libsyn_1d7e22a241 | 61.2 MB |
| S00E008__2020-05-10__animation__libsyn_d80eb33de8 | 64.6 MB |
| S00E009__2020-05-13__learning-lighting__libsyn_2f90ec2739 | 63.9 MB |
| S00E010__2020-05-17__animation-part-2__libsyn_82affef69e | 81.9 MB |
| S00E011__2020-05-20__george-mackay__libsyn_d023b8e0d9 | 117.1 MB |
| S00E012__2020-05-24__animation-dean-deblois__libsyn_28ac0da093 | 85.9 MB |
| S00E013__2020-05-27__josh-gollish-dit__libsyn_6285e0c3b6 | 106.1 MB |
| S00E014__2020-05-31__fiona-weir-casting-director__libsyn_5a3c3b2b88 | 82.7 MB |

---

## Batch History

| Date | run_id | Mode | Episodes | Instance | Notes |
|------|--------|------|----------|----------|-------|
| 2026-03-04 | `run_20260304175229__larg__dz` | test (13 ep) | 13 attempted, 8 diarized | g4dn.xlarge × 1 | First diarized run; speechbrain install bug caused ep 1-2 to lack speakers |
| 2026-03-04 | `run_20260304220257__larg__dz` | test (13 ep) | 12 done, 1 failed (SSH drop) | g4dn.xlarge × 1 | All diarized; Chris Lowe failed mid-transcription |
| 2026-03-05 | `run_20260305015618__larg__dz` | full --limit 50 | in progress | g4dn.xlarge × 1 | Includes 2 undiarized re-runs + 48 new |

---

## How to Update This Doc

This file is **auto-generated**. Regenerate after each batch completes:

```bash
python scripts/tools/transcription_report.py \
  --output documentation/guides/transcription-batch-status.md

# Then append to the Batch History table above manually,
# or commit the regenerated file to capture current state.
```

The script reads `downloads/*/transcript/runs/*/extraction_report.json` directly — no database needed.
