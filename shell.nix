{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python312
    python312Packages.pip
    python312Packages.virtualenv
  ];

  shellHook = ''
    if [ ! -d .venv ]; then
      echo "🔧 Création de l'environnement virtuel..."
      python -m venv .venv
    fi
    source .venv/bin/activate
    echo "📦 Installation des dépendances..."
    pip install -r requirements.txt -q
    echo ""
    echo "✅ Environnement Bitget Paper Trading prêt"
    echo "🐍 Python: $(python --version)"
    echo ""
    echo "Usage:"
    echo "  python main.py --mode simulate       # Test avec données simulées"
    echo "  python main.py --mode live-data      # Données réelles Bitget"
    echo "  python main.py --help                # Toutes les options"
  '';
}
