import os
import pty
import time
import glob
import sys
import codecs

# Credentials
HOST = "ZuliangdeMac-mini"
USER = "zuliangzhao"
PASS = "0605"
TARGET_DIR = "/Users/zuliangzhao/Projects/MarketMonitor"

def get_latest_backup():
    files = glob.glob("migration_tool/MarketMonitor_Migration_*.tar.gz")
    if not files: return None
    return max(files, key=os.path.getctime)

def run_interactive(cmd_list):
    print(f"🔄 Executing: {' '.join(cmd_list)}")
    
    pid, fd = pty.fork()
    if pid == 0:
        # Child
        os.execvp(cmd_list[0], cmd_list)
    else:
        # Parent
        output = b""
        password_sent = False
        
        while True:
            try:
                chunk = os.read(fd, 1024)
                if not chunk: break
                output += chunk
                sys.stdout.buffer.write(chunk)
                sys.stdout.flush()
                
                # Check for password prompt
                # Mac usually prompts "Password:" or "zuliangzhao@ZuliangdeMac-mini's password:"
                if not password_sent and (b"assword:" in chunk or b"Password:" in chunk):
                    time.sleep(0.5) # Wait a bit for buffer flush capabilities
                    os.write(fd, PASS.encode('utf-8') + b"\n")
                    password_sent = True
                    print("\n🔑 Password sent.")
                    
                # Check for fingerprint confirmation
                if b"Are you sure you want to continue connecting" in chunk:
                    os.write(fd, b"yes\n")
                    print("\n🤝 Host fingerprint accepted.")
                    
            except OSError:
                break
        
        _, status = os.waitpid(pid, 0)
        return os.WEXITSTATUS(status)

def main():
    # 1. Find Backup
    backup_file = get_latest_backup()
    if not backup_file:
        print("❌ No backup file found!")
        return
        
    print(f"📦 Found backup: {backup_file}")
    
    # 2. Create Directory
    print(f"\n1️⃣  Creating directory on remote: {TARGET_DIR}")
    # Using 'ssh' to mkdir
    # Note: Using .local as fallback if plain fails might be good, but let's stick to input first.
    # We'll try the provided host.
    ret = run_interactive(["ssh", f"{USER}@{HOST}", f"mkdir -p {TARGET_DIR}"])
    
    if ret != 0:
        print("⚠️  SSH Connection Failed. Retrying with .local suffix...")
        HOST_LOCAL = f"{HOST}.local"
        ret = run_interactive(["ssh", f"{USER}@{HOST_LOCAL}", f"mkdir -p {TARGET_DIR}"])
        if ret != 0:
            print("❌ Connection failed. Please check hostname/IP.")
            return
        else:
            print("✅ Verified .local hostname works.")
            active_host = HOST_LOCAL
    else:
        active_host = HOST

    # 3. Transfer Tarball
    print(f"\n2️⃣  Transferring Backup File ({os.path.getsize(backup_file)/1024/1024:.2f} MB)...")
    # scp local remote
    ret = run_interactive(["scp", backup_file, f"{USER}@{active_host}:{TARGET_DIR}/"])
    if ret != 0:
        print("❌ SCP Failed.")
        return

    # 4. Transfer Install Script
    print("\n3️⃣  Transferring Install Script...")
    ret = run_interactive(["scp", "migration_tool/install_on_mac.sh", f"{USER}@{active_host}:{TARGET_DIR}/"])
    
    # 5. Extract and Setup
    print("\n4️⃣  Remote Setup (Unzip & Install)...")
    remote_cmd = f"cd {TARGET_DIR} && tar -xzvf {os.path.basename(backup_file)} && chmod +x install_on_mac.sh"
    ret = run_interactive(["ssh", f"{USER}@{active_host}", remote_cmd])
    
    if ret == 0:
        print("\n✅  Migration Files Transferred & Extracted!")
        print(f"👉 Now on your Mac ({active_host}), open Terminal and run:")
        print(f"   cd {TARGET_DIR}")
        print("   ./install_on_mac.sh")
    else:
        print("\n⚠️  Remote extraction failed.")

if __name__ == "__main__":
    main()
