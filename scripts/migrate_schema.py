from utils.database import init_db

if __name__ == "__main__":
    print("Running DB Init (Migration)...")
    init_db()
    print("Done.")
