import os
import sys
import time
import socket
import threading
import webbrowser

# Add backend directory to path so uvicorn can find app_backend and main
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
sys.path.insert(0, backend_dir)

def find_free_port():
    """Find an available port dynamically, starting from 8000."""
    port = 8000
    while port < 9000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except socket.error:
                port += 1
    return 8000

def start_backend(port):
    """Starts the FastAPI backend using Uvicorn."""
    import uvicorn
    # Change working directory to backend so config and uploads are resolved correctly
    os.chdir(backend_dir)
    uvicorn.run("main:app", host="127.0.0.1", port=port, log_level="warning")

def main():
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    
    print("=" * 60)
    print("      COMPINTEL - DESKTOP APPLIKASI LAUNCHER")
    print("=" * 60)
    print(f"[*] Memulai server backend pada: {url}")
    
    # Start FastAPI backend in a background thread
    server_thread = threading.Thread(target=start_backend, args=(port,), daemon=True)
    server_thread.start()
    
    # Wait for the backend to start up
    time.sleep(1.5)
    
    # Try to open in pywebview desktop window
    try:
        import webview
        print("[+] Membuka jendela aplikasi desktop...")
        webview.create_window(
            title="COMPINTEL - Sistem Analisis Pencocokan Produk Hybrid",
            url=url,
            width=1366,
            height=768,
            resizable=True,
            min_size=(1024, 768)
        )
        webview.start()
        print("[-] Aplikasi desktop ditutup. Menghentikan server...")
        os._exit(0)
    except ImportError:
        # Fallback to default web browser if pywebview is not installed
        print("[!] pywebview tidak terinstall. Membuka di browser bawaan Anda...")
        webbrowser.open(url)
        
        # Keep the main thread alive since the server thread is a daemon
        print("[*] Tekan Ctrl+C di terminal ini untuk mematikan server.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[-] Mematikan server...")
            os._exit(0)

if __name__ == "__main__":
    main()
