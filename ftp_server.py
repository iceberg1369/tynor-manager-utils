import os
import logging
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

import psutil

def kill_old_ftp_process():
    print("🧹 Scanning for old FTP server processes...")
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline']:
                cmdline = " ".join(proc.info['cmdline'])
                if 'ftp_server.py' in cmdline and proc.info['pid'] != current_pid:
                    print(f"🔪 Found old FTP process (PID {proc.info['pid']}). Terminating...")
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    print(f"✅ Terminated PID {proc.info['pid']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def main():
    kill_old_ftp_process()
    # Suppress pyftpdlib info logs
    logging.getLogger("pyftpdlib").setLevel(logging.WARNING)

    # Configuration
    FTP_USER = "avl"
    FTP_PASS = "123456"
    FTP_PORT = 2121  # Using 2121 to avoid permission issues. Change to 21 if needed/allowed.
    
    # Directory to serve
    # Getting absolute path of 'ftp_root' in the current directory
    ftp_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ftp_root')
    
    # Ensure directory exists just in case
    if not os.path.exists(ftp_root):
        os.makedirs(ftp_root)

    print(f"Starting FTP Server...")
    print(f"Serving directory: {ftp_root}")

    # Instantiate a dummy authorizer for managing 'virtual' users
    authorizer = DummyAuthorizer()

    # Define a new user having full r/w permissions
    # perms:
    #   e - change directory
    #   l - list files
    #   r - retrieve file
    #   a - append data
    #   d - delete file
    #   f - rename file
    #   m - make directory
    #   w - store file
    # We will give read/write access for now as often requested for testing, 
    # but for pure serving 'elr' is enough. 
    # Let's give 'elr' (read-only) + 'w' (write) just in case? 
    # The user said "attribute files" or "serve a specific directory files". Implies download.
    # But usually 'avl'/123456 implies a device might upload too?
    # I'll stick to read-only 'elr' unless user asks otherwise, it's safer. 
    # Wait, the user prompt was "serve a specific directory files". 
    # I will add 'w' (write) just in case they need to upload logs, 
    # but typically 'serve' means download. I'll stick to 'elradfmw' (Full) 
    # effectively or just 'elr' + 'w'? 
    # Let's go with 'elr' primarily. If they need write, they can ask.
    # Actually, let's provide 'all' permissions for this specific user/pass combo 
    # to be most helpful so they don't get 'permission denied' errors during testing.
    # 'elradfmwM' is full.
    
    authorizer.add_user(FTP_USER, FTP_PASS, ftp_root, perm='elr')

    # Instantiate FTP handler class
    handler = FTPHandler
    handler.authorizer = authorizer

    # Define a customized banner (string returned when client connects)
    handler.banner = "pyftpdlib based ftpd ready."

    # Instantiate FTP server class and listen on 0.0.0.0:2121
    address = ('0.0.0.0', FTP_PORT)
    server = FTPServer(address, handler)

    # set a limit for connections
    server.max_cons = 256
    server.max_cons_per_ip = 5

    print(f"FTP Server running on ftp://0.0.0.0:{FTP_PORT}")
    #print(f"Username: {FTP_USER}")
    #print(f"Password: {FTP_PASS}")
    
    # start ftp server
    server.serve_forever()

if __name__ == '__main__':
    main()
