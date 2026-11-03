import os

if __name__ == "__main__":
    pid = os.getpid()
    # Determine the directory of this script
    script_dir = os.path.abspath(os.path.dirname(__file__))
    pid_path = os.path.join(script_dir, "pid_sortie.txt")
    # Write PID to file
    with open(pid_path, "w") as f:
        f.write(str(pid))
    # Print PID
    print(pid)
