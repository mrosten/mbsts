from mbsts_15m_v4.main import main

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        with open("launcher_crash.txt", "w") as f:
            f.write(traceback.format_exc())
        print("CRASHED! See launcher_crash.txt")
        input("Press Enter to continue...")
