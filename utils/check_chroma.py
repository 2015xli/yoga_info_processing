import os, fcntl
CHROMA_PERSIST_DIR = "/home/xli/NAS/home/bin/yoga-info-processing/graphrag/chroma_db/"

def check_chroma_dir_permission():
    test_file = os.path.join(CHROMA_PERSIST_DIR, "locktest.txt")
    with open(test_file, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print("✅ Locking supported!")
            fcntl.flock(f, fcntl.LOCK_UN)
        except IOError:
            print("❌ Locking NOT supported on this filesystem!")


if __name__ == "__main__":

    check_chroma_dir_permission()