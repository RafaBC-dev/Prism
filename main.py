
import sys
import os

# Asegurar que el directorio raíz del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def main():
    from ui.shell import PrismShell
    app = PrismShell()
    app.mainloop()

if __name__ == "__main__":
    sys.exit(main())
