{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python312
    python312Packages.pip
    python312Packages.virtualenv
    stdenv.cc.cc.lib   # libstdc++.so.6 requis par numpy/pandas
    zlib               # libz.so.1 requis par numpy
  ];

  # Exposer libstdc++ et zlib dans le chemin dynamique du venv
  shellHook = ''
    export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:$LD_LIBRARY_PATH

    if [ ! -d .venv ]; then
      echo "🔧 Création de l'environnement virtuel..."
      python -m venv .venv
    fi
    source .venv/bin/activate

    pip install -r requirements.txt -q

    echo ""
    echo "✅ Environnement Bitget Paper Trading prêt"
    echo "🐍 Python: $(python --version)"
    echo ""
    echo "Usage:"
    echo "  python main.py --mode simulate          # Backtest rapide (données mock)"
    echo "  python main.py --mode backtest --days 60 # Backtest données Bitget réelles"
    echo "  python main.py --mode paper --timeframe 1h  # Paper trading temps réel 24/7"
    echo "  python main.py --status                 # État du portfolio sauvegardé"
    echo "  python main.py --profile                # Profil exchange live"
    echo "  python main.py --help                   # Toutes les options"
  '';
}
