import os
import sys
import tkinter
import _tkinter

print("\n--- COPIA DESDE AQUÍ ---")
print(f"PYTHON_EXE: {sys.executable}")
print(f"DLL_FOLDER: {os.path.dirname(_tkinter.__file__)}")
try:
    print(f"TCL_LIB: {tkinter.Tcl().eval('info library')}")
except:
    print("TCL_LIB: No se pudo determinar por eval")

# Verificamos si las DLLs existen en la raíz
for dll in ["tcl86t.dll", "tk86t.dll"]:
    path = os.path.join(os.path.dirname(sys.executable), dll)
    print(f"{dll} en raíz: {os.path.exists(path)}")

print("--- HASTA AQUÍ ---\n")