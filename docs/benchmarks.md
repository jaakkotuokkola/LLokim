# Benchmark Results

These are real synthetic measurements captured from the LLokim benchmark utility.
They do not represent journal collection or AI inference.

## Environment

- LLokim: 0.1.0
- Python: 3.12.3
- Linux: 6.8.0-149-generic
- Architecture: x86_64
- AI inference: not run

## Results

| Events | Parse | Analyze | Report | Total | Peak RSS |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.001792 s | 0.004602 s | 0.009817 s | 0.016211 s | 208.56 MiB |
| 1,000 | 0.009537 s | 0.030242 s | 0.057176 s | 0.096955 s | 208.56 MiB |
| 5,000 | 0.089095 s | 0.175873 s | 0.224498 s | 0.489465 s | 208.56 MiB |
| 10,000 | 0.261524 s | 0.454675 s | 0.145779 s | 0.861978 s | 208.56 MiB |

Measurements use one iteration in this run. Re-run with the installed
benchmark utility for host-specific results:

```bash
llokim-benchmark --iterations 3
```
