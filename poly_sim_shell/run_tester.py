import os
from mbsts_tester_v4.tester_app import TesterApp

def main():
    # Ensure logs directory exists
    if not os.path.exists("logs"):
        os.makedirs("logs")
        
    print("Starting Tester TUI...")
    app = TesterApp()
    app.run()

if __name__ == "__main__":
    main()
