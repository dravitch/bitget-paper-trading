# Bitget Paper Trading

A paper trading engine for Bitget futures, written in Python. Backtest strategies on real market data or run a 24/7 simulated portfolio without risking capital.

---

## Features

- **3 run modes**: quick simulation (mock data), historical backtest (real Bitget candles), real-time paper trading
- **Built-in strategies**: RSI mean-reversion, Moving Average crossover, with multi-strategy consensus
- **Portfolio engine**: position averaging, commission tracking, PnL, max drawdown, win rate
- **State persistence**: portfolio survives restarts via JSON snapshots
- **Exchange profiling**: live spread, fees, and liquidity snapshot before trading
- **NixOS ready**: reproducible dev environment via `shell.nix`

---

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.11 |
| NumPy | 1.26.x (`< 2.0`) |
| pandas | 2.x |
| ccxt | 4.3+ |

> **Note — old CPU compatibility**: NumPy 2.x requires x86_v2 instructions (SSE4.2, POPCNT). On pre-2010 hardware use `numpy<2.0`. The `requirements.txt` already pins this.

---

## Quick start

### With Nix (recommended)

```bash
git clone <repo-url>
cd bitget-paper-trading
nix-shell            # creates .venv, installs deps, sets LD_LIBRARY_PATH
```

### Without Nix

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### API credentials (optional — only for backtest/paper modes)

```bash
cp .env.example .env
# fill in BITGET_API_KEY, BITGET_SECRET, BITGET_PASSWORD
```

---

## Usage

```bash
# Fast smoke test — no API keys, no network
python main.py --mode simulate

# Backtest on real Bitget data (read-only API)
python main.py --mode backtest --days 60 --timeframe 1h

# Real-time paper trading, runs indefinitely
python main.py --mode paper --timeframe 1h

# Options
python main.py --mode backtest --strategy rsi --symbols BTC/USDT:USDT ETH/USDT:USDT
python main.py --profile          # exchange spread / fee / liquidity snapshot
python main.py --status           # portfolio state from last run
python main.py --reset            # clear saved state
python main.py --help
```

### Full CLI reference

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `simulate` | `simulate` / `backtest` / `paper` |
| `--timeframe` | `1d` | `1m` `5m` `15m` `30m` `1h` `4h` `1d` |
| `--days` | 30 | Candles look-back window |
| `--capital` | 10000 | Starting capital (USDT) |
| `--symbols` | BTC ETH | Space-separated symbol list |
| `--strategy` | `rsi` | `rsi` / `moving_average` |
| `--state-file` | auto | Custom path for state JSON |
| `--reset` | — | Wipe saved state before start |
| `--profile` | — | Print exchange profile and exit |
| `--status` | — | Print saved portfolio state and exit |
| `--verbose` | — | Debug-level logging |

---

## Project structure

```
bitget-paper-trading/
├── main.py                     # CLI entry point
├── requirements.txt
├── shell.nix                   # NixOS dev environment
├── config/
│   └── default.yaml            # All trading parameters
├── adapters/
│   ├── base.py                 # Abstract exchange interface
│   ├── mock.py                 # Deterministic mock data (no API)
│   └── bitget.py               # Bitget via ccxt (read-only)
├── core/
│   └── signal_generator.py     # RSI + MA strategies, consensus engine
├── paper_trading/
│   ├── engine.py               # Backtest / paper trading orchestrator
│   ├── portfolio.py            # Virtual portfolio (orders, positions, PnL)
│   ├── performance.py          # Metrics, equity curve plot, report
│   └── state.py                # JSON persistence
└── tests/
    └── test_portfolio.py       # Portfolio unit tests
```

---

## Configuration

Edit `config/default.yaml` to tune:

```yaml
trading:
  initial_capital: 10000
  position_size_pct: 0.30      # 30 % of capital per trade
  symbols:
    - BTC/USDT:USDT
    - ETH/USDT:USDT

strategy:
  rsi:
    period: 14
    oversold: 30
    overbought: 70
  moving_average:
    fast: 20
    slow: 50
```

---

## Running tests

```bash
pytest tests/ -v
```

---

## License

MIT
