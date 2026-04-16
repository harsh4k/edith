import os
import time
import platform
from datetime import datetime
import psutil

# Optional GPU
try:
    import GPUtil
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False


# ===== COLORS (WARM THEME) =====
W = "\033[97m"   # white
Y = "\033[93m"   # yellow
O = "\033[91m"   # orange/red
R = "\033[0m"    # reset


# ===== CLEAR =====
def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


# ===== SYSTEM STATS =====
def get_stats():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    cache = getattr(ram, "cached", 0) / (1024**3)

    # temperature
    try:
        temps = psutil.sensors_temperatures()
        cpu_temp = list(temps.values())[0][0].current
    except:
        cpu_temp = "N/A"

    # gpu
    if GPU_AVAILABLE:
        try:
            gpu = GPUtil.getGPUs()[0]
            gpu_load = int(gpu.load * 100)
            gpu_temp = gpu.temperature
        except:
            gpu_load, gpu_temp = "N/A", "N/A"
    else:
        gpu_load, gpu_temp = "N/A", "N/A"

    return {
        "cpu": cpu,
        "ram_used": round(ram.used / (1024**3), 2),
        "ram_total": round(ram.total / (1024**3), 2),
        "disk_used": round(disk.used / (1024**3), 2),
        "disk_total": round(disk.total / (1024**3), 2),
        "cache": round(cache, 2),
        "cpu_temp": cpu_temp,
        "gpu": gpu_load,
        "gpu_temp": gpu_temp
    }


# ===== DASHBOARD =====
def dashboard(status="ACTIVE"):
    clear()
    stats = get_stats()

    time_now = datetime.now().strftime("%H:%M:%S")
    date_now = datetime.now().strftime("%d-%m-%Y")

    print(Y + "="*50)
    print("         EDITH TERMINAL")
    print("="*50 + R)

    print(O + f"STATUS: {status}\n" + R)

    print(Y + "[ SYSTEM STATS ]" + R)
    print(f"CPU   : {stats['cpu']}%")
    print(f"GPU   : {stats['gpu']}%")
    print(f"RAM   : {stats['ram_used']} / {stats['ram_total']} GB")
    print(f"DISK  : {stats['disk_used']} / {stats['disk_total']} GB")

    print(f"\nTEMP  : CPU {stats['cpu_temp']}°C | GPU {stats['gpu_temp']}°C")
    print(f"CACHE : {stats['cache']} GB")

    print(Y + "\n[ INFO ]" + R)
    print(f"TIME  : {time_now}")
    print(f"DATE  : {date_now}")
    print(f"OS    : {platform.system()}")

    print(Y + "\n[ COMMANDS ]" + R)
    print("help   cpu   ram   disk   temp   monitor   stop   clear   exit")

    print(Y + "\n" + "-"*50 + R)


# ===== MAIN LOOP =====
def run():
    dashboard()
    monitoring = False

    while True:
        cmd = input(W + "EDITH > " + R).lower()

        if cmd == "help":
            print("help, cpu, ram, disk, temp, monitor, stop, clear, exit")

        elif cmd == "clear":
            dashboard()

        elif cmd == "cpu":
            print(f"CPU Usage: {psutil.cpu_percent()}%")

        elif cmd == "ram":
            ram = psutil.virtual_memory()
            print(f"RAM: {round(ram.used/(1024**3),2)} / {round(ram.total/(1024**3),2)} GB")

        elif cmd == "disk":
            disk = psutil.disk_usage('/')
            print(f"Disk: {round(disk.used/(1024**3),2)} / {round(disk.total/(1024**3),2)} GB")

        elif cmd == "temp":
            stats = get_stats()
            print(f"CPU Temp: {stats['cpu_temp']}°C | GPU Temp: {stats['gpu_temp']}°C")

        elif cmd == "monitor":
            monitoring = True
            print("Live monitor started (type 'stop')")

            while monitoring:
                dashboard("MONITORING")
                time.sleep(2)

        elif cmd == "stop":
            monitoring = False
            dashboard()

        elif cmd == "exit":
            print("Shutting down EDITH...")
            break

        else:
            print("Unknown command")


# ===== START =====
if __name__ == "__main__":
    run()