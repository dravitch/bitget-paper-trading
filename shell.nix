{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python311            # 3.12 + numpy 2.x → incompatible vieux CPU (pas x86_v2)
    python311Packages.pip
    python311Packages.virtualenv
    stdenv.cc.cc.lib     # libstdc++.so.6 requis par numpy/pandas dans le venv
    zlib                 # libz.so.1 requis par numpy
  ];

  shellHook = ''
    export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.zlib}/lib:$LD_LIBRARY_PATH

    # Reconstruire le venv si la version Python a changé
    EXPECTED_PYTHON="3.11"
    if [ -d .venv ]; then
      VENV_PYTHON=$(.venv/bin/python --version 2>&1 | grep -oP '3\.\d+')
      if [ "$VENV_PYTHON" != "$EXPECTED_PYTHON" ]; then
        echo "⚠️  Venv Python $VENV_PYTHON détecté, reconstruction en Python $EXPECTED_PYTHON..."
        rm -rf .venv
      fi
    fi

    if [ ! -d .venv ]; then
      echo "🔧 Création du venv Python $EXPECTED_PYTHON..."
      python -m venv .venv
    fi
    source .venv/bin/activate

    pip install -r requirements.txt -q

    echo ""
    echo "✅ Environnement Bitget Paper Trading prêt"
    echo "🐍 Python: $(python --version)"
    echo "📦 NumPy:  $(python -c 'import numpy; print(numpy.__version__)' 2>/dev/null || echo 'non installé')"
    echo ""
    echo "Usage:"
    echo "  python main.py --mode simulate              # Backtest rapide (données mock)"
    echo "  python main.py --mode backtest --days 60    # Backtest données Bitget réelles"
    echo "  python main.py --mode paper --timeframe 1h  # Paper trading temps réel 24/7"
    echo "  python main.py --status                     # État du portfolio sauvegardé"
    echo "  python main.py --profile                    # Profil exchange live"
    echo "  python main.py --help                       # Toutes les options"
  '';
}
