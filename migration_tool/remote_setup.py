import os
import pty
import time
import sys

# Credentials
HOST = "ZuliangdeMac-mini.local" # Auto-resolved from previous step
USER = "zuliangzhao"
PASS = "0605"
TARGET_DIR = "/Users/zuliangzhao/Projects/MarketMonitor"

def run_interactive(cmd_list):
    print(f"🔄 Executing Remote Command: {' '.join(cmd_list)}")
    
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(cmd_list[0], cmd_list)
    else:
        password_sent = False
        output_log = b""
        
        while True:
            try:
                chunk = os.read(fd, 1024)
                if not chunk: break
                output_log += chunk
                sys.stdout.buffer.write(chunk)
                sys.stdout.flush()
                
                # Check for Password prompts (SSH or Sudo)
                if b"assword:" in chunk or b"Password:" in chunk:
                    current_time = time.time()
                    # Cooldown of 2 seconds to avoid spamming the same prompt in buffer
                    if current_time - last_password_time > 2.0:
                        time.sleep(0.5)
                        os.write(fd, PASS.encode('utf-8') + b"\n")
                        last_password_time = current_time
                        print("\n🔑 Password sent.")
                
                # Handle 'Recreate venv? (y/n)' prompt from install script
                if b"Recreate venv? (y/n)" in chunk:
                    time.sleep(0.5)
                    os.write(fd, b"y\n")
                    print("\n✨ Auto-confirmed venv recreation.")

                # Handle 'Press RETURN' for Brew
                if b"Press RETURN" in chunk or b"Press ENTER" in chunk:
                     time.sleep(0.5)
                     os.write(fd, b"\n")
                     print("\n⏎ Sent RETURN key.")

            except OSError:
                break
        
        _, status = os.waitpid(pid, 0)
        return os.WEXITSTATUS(status)

def main():
    print(f"🚀 Starting Remote Setup on {HOST}...")
    
    # We pipe 'yes' into the command just in case, but run_interactive handles logic too.
    # Actually, let's trust run_interactive to handle the prompt if it appears.
    
    remote_cmd = f"cd {TARGET_DIR} && ./install_on_mac.sh"
    
    # SSH execution
    # -t forces pseudo-tty allocation which helps with interactive prompts
    ret = run_interactive(["ssh", "-t", f"{USER}@{HOST}", remote_cmd])
    
    if ret == 0:
        print("\n✅ Remote Setup Completed Successfully!")
    else:
        print(f"\n❌ Remote Setup Failed with code {ret}")

if __name__ == "__main__":
    main()
