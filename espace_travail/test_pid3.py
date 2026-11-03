import os

pid = os.getpid()
# Write PID to file in the same directory
file_path = os.path.join(os.path.dirname(__file__), 'pid_sortie3.txt')
with open(file_path, 'w') as f:
    f.write(str(pid))
# Print PID
print(pid)
