# Cloudflare Edge IP Optimizer (本地优选工具)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

A high-performance local Cloudflare CDN edge IP optimizer and latency benchmarking toolkit designed to identify, test, and filter the lowest-latency edge nodes for personal acceleration and network diagnostics.

---

## 🌟 Features

- **Multi-Source Aggregation**: Merges and cleans candidate node pools dynamically.
- **Precision RTT & Bandwidth Testing**: Real-time concurrent socket probing and HTTP throughput estimation.
- **Autonomous Filtering**: Filters out high-jitter endpoints and unifies region allocations (HK, TW, JP, SG, US, etc.).
- **Clean Output Architecture**: Automatically updates and exports formatted endpoints to `ip.txt`, `ip_global.txt`, and structured `ip_detail.json` / `ip_detail.csv`.
- **Lightweight & Portable**: Fully compatible with CLI environments, headless VPS, and desktop runtimes.

---

## 🚀 Quick Start

### 1. Requirements

- Python 3.9+
- Standard library dependencies (`urllib`, `socket`, `concurrent.futures`, `json`, `csv`)

### 2. Execution

Clone the repository and run the local scanner:

```bash
git clone https://github.com/NMLGB41/bendiyouxuan.git
cd bendiyouxuan
python3 run_local.py
```

Results will be automatically benchmarked and written to:
- `ip.txt` — Plain list of fastest nodes
- `ip_detail.json` — Detailed diagnostic payload with latency and region tagging

---

## 📄 License

This project is open-sourced under the [MIT License](LICENSE). Contributions, issues, and feature requests are welcome!
