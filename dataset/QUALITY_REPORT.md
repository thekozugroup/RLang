# RLang Dataset Quality Report

## Summary

- **Total optimized traces:** 2790
- **Rejected traces:** 167
- **Validation pass rate:** 94.4%

## Compression Ratios (English tokens / RLang tokens)

- **Average:** 3.09x
- **Median:** 2.51x
- **Min:** 0.20x
- **Max:** 18.73x

### Compression Ratio Distribution

| Bucket | Count | % |
|--------|------:|---:|
| <1x (expansion) | 327 | 11.7% |
| 1-2x | 675 | 24.2% |
| 2-3x | 724 | 25.9% |
| 3-5x | 614 | 22.0% |
| 5-10x | 440 | 15.8% |
| 10x+ | 29 | 1.0% |

## Compression by Domain

| Domain | Traces | Avg Compression |
|--------|-------:|----------------:|
| code | 131 | 1.59x |
| math | 1944 | 2.22x |
| reasoning | 715 | 5.74x |

## Compression by Difficulty

| Difficulty | Traces | Avg Compression |
|------------|-------:|----------------:|
| medium | 2175 | 2.46x |
| hard | 496 | 5.59x |
| phd | 119 | 4.23x |

## Top 10 Most Common RLang Operators

| Rank | Operator | Occurrences |
|-----:|----------|------------:|
| 1 | `sup()` | 12,963 |
| 2 | `req()` | 8,593 |
| 3 | `obs()` | 5,643 |
| 4 | `verify()` | 5,424 |
| 5 | `cause()` | 3,920 |
| 6 | `conf()` | 2,790 |
| 7 | `resolve()` | 2,790 |
| 8 | `assert()` | 2,790 |
| 9 | `hedge()` | 2,790 |
| 10 | `reject()` | 2,790 |

## Average Phase Distribution

| Phase | Avg Statements | % of Trace |
|-------|---------------:|-----------:|
| Frame | 3.4 | 19.4% |
| Explore | 8.0 | 46.4% |
| Verify | 1.9 | 11.2% |
| Decide | 4.0 | 23.1% |

## Confidence Value Statistics

- **Total confidence annotations:** 15434
- **Average:** 0.739
- **Median:** 0.750
- **Min:** 0.500
- **Max:** 0.950

### Confidence Distribution

| Range | Count | % |
|-------|------:|---:|
| 0.0-0.5 (low) | 3 | 0.0% |
| 0.5-0.7 (moderate) | 1344 | 8.7% |
| 0.7-0.85 (high) | 13997 | 90.7% |
| 0.85-0.95 (very high) | 93 | 0.6% |
| 0.95-1.0 (near certain) | 93 | 0.6% |

## RLang Token Count Distribution

| Bucket | Count | % |
|--------|------:|---:|
| 0-50 | 0 | 0.0% |
| 51-100 | 702 | 25.2% |
| 101-200 | 1564 | 56.1% |
| 201-500 | 454 | 16.3% |
| 501-1K | 62 | 2.2% |
| 1K+ | 8 | 0.3% |

## English Token Count Distribution

| Bucket | Count | % |
|--------|------:|---:|
| 0-100 | 320 | 11.5% |
| 101-500 | 1682 | 60.3% |
| 501-1K | 162 | 5.8% |
| 1K-2K | 503 | 18.0% |
| 2K-5K | 122 | 4.4% |
| 5K+ | 1 | 0.0% |
