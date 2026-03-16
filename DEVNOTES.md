# DEVNOTES — Bitget Paper Trading
> Notes personnelles de session. Ne pas committer si ce fichier contient des credentials.

---

## Environnement de travail

### Machine cible
- **Host**: Proxmox VM sur Dell PowerEdge T100
- **CPU**: pré-2010, **pas de support x86_v2** (pas de SSE4.2 / POPCNT)
- **OS**: NixOS (nix-shell pour l'environnement Python)
- **Shell de session**: tmux recommandé (voir section ci-dessous)

### Stack validée
| Composant | Version | Raison |
|-----------|---------|--------|
| Python | 3.11 | numpy 2.x ne supporte pas Python 3.13 ; 3.11 = sweet spot |
| NumPy | 1.26.4 | Dernière version sans x86_v2. NumPy 2.x → `RuntimeError: X86_V2` |
| pandas | 2.x | Compatible numpy 1.26.x |
| NixOS | `python311` dans shell.nix | libstdc++.so.6 via `stdenv.cc.cc.lib` dans `LD_LIBRARY_PATH` |

---

## Setup tmux pour session longue

```bash
# Créer une session nommée
tmux new-session -s trading

# Dans la session :
cd ~/               # le projet est à la racine home (rootdir /home/pulse)
nix-shell           # lance le venv Python 3.11 automatiquement

# Panneaux utiles (Ctrl+B suivi de %)
# Panneau gauche : code / git
# Panneau droit  : python main.py --mode paper ...

# Se détacher sans tuer le process
Ctrl+B  d

# Rattacher plus tard
tmux attach -t trading

# Lister les sessions
tmux ls
```

### Commandes paper trading à lancer dans tmux
```bash
# Backtest rapide pour valider l'env
python main.py --mode simulate

# Backtest réel (nécessite .env avec clés API read-only)
python main.py --mode backtest --days 60 --timeframe 1h --verbose

# Paper trading continu (laisser tourner dans tmux)
python main.py --mode paper --timeframe 1h
```

---

## Historique des problèmes résolus

### Session 2026-03-16

| Problème | Cause | Fix appliqué |
|----------|-------|--------------|
| `ImportError: libstdc++.so.6 not found` | `shell.nix` n'exposait pas gcc libs | Ajout `stdenv.cc.cc.lib` + `LD_LIBRARY_PATH` dans `shell.nix` |
| `RuntimeError: X86_V2` numpy 2.x | CPU incompatible avec les instructions x86_v2 | `python311` dans `shell.nix` + `numpy<2.0` dans `requirements.txt` |
| `--mode live-data` invalide | Mode n'existait pas dans l'argparse | Documenté — modes valides : `simulate`, `backtest`, `paper` |
| Venv reconstruit automatiquement | Détection version Python dans `shellHook` | `shell.nix` supprime `.venv` si Python version ≠ 3.11 |

---

## Ce qui reste à faire

### Priorité haute

- [ ] **Valider les tests unitaires**
  ```bash
  pytest tests/ -v
  ```
  - `test_portfolio.py` couvre : buy/sell, positions, PnL, win rate, drawdown
  - Objectif : tous verts avant d'itérer sur les stratégies

- [ ] **Tester le mode backtest réel**
  ```bash
  cp .env.example .env      # remplir les clés API Bitget (read-only suffit)
  python main.py --mode backtest --days 30 --timeframe 1h
  ```
  - Vérifier que `BitgetAdapter` récupère bien les OHLCV via ccxt

- [ ] **Valider le mode paper**
  ```bash
  python main.py --mode paper --timeframe 1h
  # Laisser tourner 2-3 cycles (1h chacun) dans tmux
  python main.py --status    # vérifier que le state est bien persisté
  ```

### Priorité moyenne

- [ ] **TA-lib** — actuellement désactivé dans `requirements.txt`
  - Nécessite la lib C `ta-lib` : `pkgs.ta-lib` à ajouter dans `shell.nix`
  - Décommenter `ta-lib>=0.4.28` dans `requirements.txt`
  - Ajoute des indicateurs supplémentaires : MACD, Bollinger Bands, ATR

- [ ] **Consensus multi-stratégies** — `SignalGenerator` a la structure mais à vérifier
  - Tester avec `--strategy rsi` et `--strategy moving_average` en parallèle
  - Implémenter pondération par `SignalStrength` (WEAK/MEDIUM/STRONG)

- [ ] **Rich live display** — dashboard temps réel dans le terminal
  - `rich.live` + `rich.table` pour afficher portfolio + signaux en cours
  - Remplace les `print()` séquentiels du mode paper

- [ ] **Stop-loss / take-profit automatique**
  - `TradingSignal` a déjà `stop_loss` et `take_profit` dans `core/signal_generator.py`
  - À brancher dans `engine._execute()` pour fermer positions automatiquement

### Priorité basse / future

- [ ] **Notifications Telegram/Discord** — alertes sur signaux forts et trades executés
- [ ] **Systemd service** — lancer le mode paper au démarrage de la VM
- [ ] **Grid search backtest** — optimiser les paramètres RSI/MA par symbol
- [ ] **Rapport HTML** — exporter les résultats `PerformanceTracker` en HTML interactif

---

## Vision architecturale — objectif final

```
┌─────────────────────────────────────────────────────────────────┐
│                     BITGET PAPER TRADING                        │
│                    Architecture cible v2                        │
└─────────────────────────────────────────────────────────────────┘

                         ┌──────────────┐
                         │   main.py    │  CLI + orchestrateur
                         └──────┬───────┘
                                │
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
   ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐
   │  MockAdapter │   │  BitgetAdapter   │   │ FutureAdapter│
   │  (tests/CI)  │   │  (ccxt, ro)      │   │  (extensible)│
   └──────────────┘   └────────┬─────────┘   └──────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   DataPipeline      │
                    │  OHLCV + orderbook  │
                    │  normalisation      │
                    └──────────┬──────────┘
                               │
              ┌────────────────▼──────────────────┐
              │          SignalGenerator           │
              │  ┌─────────┐  ┌──────────────┐    │
              │  │   RSI   │  │  MovingAvg   │    │
              │  └────┬────┘  └──────┬───────┘    │
              │       │   Consensus   │            │
              │       └──────┬────────┘            │
              │         ┌────▼─────┐               │
              │         │TA-lib    │ (phase 2)      │
              │         │MACD, BB  │                │
              │         └──────────┘               │
              └──────────────┬─────────────────────┘
                             │ TradingSignal
                    ┌────────▼────────┐
                    │  RiskManager    │  ← à créer (phase 2)
                    │  stop-loss      │
                    │  position size  │
                    │  max drawdown   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  PaperEngine    │
                    │  backtest       │
                    │  paper 24/7     │
                    └────────┬────────┘
                             │
           ┌─────────────────┼──────────────────┐
           ▼                 ▼                  ▼
   ┌──────────────┐  ┌──────────────┐  ┌───────────────┐
   │  Portfolio   │  │  State.json  │  │ Performance   │
   │  Manager     │  │  persistence │  │ Tracker       │
   └──────────────┘  └──────────────┘  └───────┬───────┘
                                               │
                              ┌────────────────▼────────┐
                              │       Outputs           │
                              │  Rich dashboard (tmux)  │
                              │  Equity curve (pyplot)  │
                              │  Rapport texte/HTML     │
                              │  Alertes Telegram       │
                              └─────────────────────────┘
```

### Phases de développement

```
Phase 1 ✅ — Fondation (session actuelle)
  Env NixOS, adaptateurs, stratégies RSI/MA, portfolio, persistence

Phase 2 — Signal enrichi
  TA-lib (MACD, Bollinger, ATR), consensus pondéré, stop/TP automatique

Phase 3 — Robustesse
  RiskManager, max drawdown guard, position sizing dynamique,
  Rich live dashboard, tests d'intégration

Phase 4 — Production
  Systemd service, logs structurés, alertes Telegram/Discord,
  Health check endpoint

Phase 5 — Optimisation
  Grid search backtest, Sharpe/Sortino, rapport HTML interactif,
  comparaison multi-stratégies
```

---

## Commandes de reprise rapide

```bash
# 1. Rattacher la session tmux si elle existe
tmux attach -t trading    # ou : tmux new-session -s trading

# 2. Entrer dans l'env Nix
cd ~
nix-shell

# 3. Vérifier que l'env est sain
python -c "import numpy; print(numpy.__version__)"   # doit afficher 1.26.x
pytest tests/ -v                                     # doit être tous verts

# 4. Reprendre là où on s'est arrêté
git log --oneline -5      # voir les derniers commits
git status                # s'assurer qu'on est sur la bonne branche

# 5. Lancer le backtest de validation
python main.py --mode backtest --days 30 --timeframe 1h --verbose
```

---

## Branche de développement
```
claude/explore-code-cloud-Hm5n9
```
