import subprocess
import sys

def install(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"Successfully installed {package}")
    except Exception as e:
        print(f"Failed to install {package}: {e}")

if __name__ == "__main__":
    install("Pillow")
