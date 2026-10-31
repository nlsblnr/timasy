"""Gemeinsame Hilfen für die Tests."""
import sys
from pathlib import Path

# Projektwurzel in den Suchpfad, damit "import backend" funktioniert.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
