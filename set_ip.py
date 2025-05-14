#!/usr/bin/env python3
import subprocess
import os
import re
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom  # Để ghi XML đẹp hơn (tùy chọn)

# ----- Cấu hình cần kiểm tra/thay đổi -----
# Tên interface mạng chính của máy host cần lấy IP
NETWORK_INTERFACE = "wlp0s20f3"  # !!! THAY ĐỔI NẾU CẦN !!!

# Danh sách tên các thuộc tính trong hdfs-site.xml cần kiểm tra/cập nhật IP
HDFS_PROPERTIES_TO_UPDATE = [
    "dfs.datanode.address",
    "dfs.datanode.http.address",
    "dfs.datanode.ipc.address",
    "dfs.namenode.rpc-address",
    "dfs.namenode.http-address"
]

# Danh sách tên các thuộc tính trong core-site.xml cần kiểm tra/cập nhật IP
CORE_PROPERTIES_TO_UPDATE = [
    "fs.defaultFS"  # Thuộc tính chính trong core-site.xml
]

# Đường dẫn đến thư mục cài đặt Hadoop
HADOOP_HOME = "/home/phuc/hadoop"
# ------------------------------------------

# Đường dẫn được suy ra
HADOOP_CONF_DIR = os.path.join(HADOOP_HOME, "etc/hadoop")
HDFS_SITE_FILE = os.path.join(HADOOP_CONF_DIR, "hdfs-site.xml")
# CORE_SITE_FILE = os.path.join("/home/phuc/codeproject/bigdata/hadoop", "core-site.xml")  # Thêm core-site.xml
HADOOP_SBIN_DIR = os.path.join(HADOOP_HOME, "sbin")
STOP_DFS_CMD = os.path.join(HADOOP_SBIN_DIR, "stop-dfs.sh")
START_DFS_CMD = os.path.join(HADOOP_SBIN_DIR, "start-dfs.sh")
START_YARN_CMD = os.path.join(HADOOP_SBIN_DIR, "start-yarn.sh")

# Regex để trích xuất IP từ giá trị dạng "ip:port" hoặc "hdfs://ip:port"
IP_PORT_REGEX = re.compile(r'^(?:hdfs://)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::\d+)?$')

def get_current_ip(interface):
    """Lấy địa chỉ IPv4 hiện tại của interface mạng được chỉ định."""
    print(f"Attempting to get IP for interface: {interface}")
    try:
        result = subprocess.run(
            ['ip', '-4', 'addr', 'show', interface],
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/\d+', result.stdout)
        if match:
            ip_address = match.group(1)
            print(f"Successfully found current host IP: {ip_address}")
            return ip_address
        else:
            print(f"Error: Could not parse IPv4 address for interface {interface}.")
            return None
    except Exception as e:
        print(f"An error occurred while getting IP: {e}")
        return None

def update_config_file_dynamically(current_host_ip, config_file, properties_to_update):
    if not current_host_ip:
        print("Cannot update config: Current host IP not found.")
        return False

    print(f"Checking configuration file: {config_file}")
    try:
        # Phân tích file XML
        tree = ET.parse(config_file)
        root = tree.getroot()
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_file}")
        return False
    except ET.ParseError as e:
        print(f"Error parsing XML file {config_file}: {e}")
        return False
    except Exception as e:
        print(f"Error reading or parsing configuration file {config_file}: {e}")
        return False

    configured_ip = None
    config_needs_update = False

    # Tìm IP hiện đang cấu hình trong các thuộc tính quan trọng
    print(f"Scanning {config_file} for currently set IP addresses...")
    for prop in root.findall('.//property'):
        name_elem = prop.find('name')
        value_elem = prop.find('value')
        if name_elem is not None and value_elem is not None and name_elem.text in properties_to_update:
            current_value = value_elem.text.strip() if value_elem.text else ''
            match = IP_PORT_REGEX.match(current_value)
            if match:
                ip_in_config = match.group(1)
                print(f"  Found IP '{ip_in_config}' in property '{name_elem.text}'")
                if configured_ip is None:
                    configured_ip = ip_in_config  # Lấy IP đầu tiên tìm thấy làm IP tham chiếu
                elif configured_ip != ip_in_config:
                    print(f"  Warning: Inconsistent IP addresses found in config ('{configured_ip}' vs '{ip_in_config}'). Using the first one found for comparison.")

                # Kiểm tra xem IP này có cần cập nhật không
                if ip_in_config != current_host_ip:
                    config_needs_update = True
            else:
                print(f"  Warning: Value '{current_value}' for property '{name_elem.text}' does not match expected IP:PORT or hdfs://IP:PORT format.")

    if not configured_ip:
        print(f"Could not find a valid configured IP address in the specified properties of {config_file}. No update possible.")
        return False

    print(f"Detected configured IP in {config_file} as: {configured_ip}")
    print(f"Current host IP is:      {current_host_ip}")

    if not config_needs_update:
        print(f"Configured IP in {config_file} matches current host IP, or no updates needed for found IPs. No changes made.")
        return False

    # --- Thực hiện cập nhật ---
    print(f"\nUpdating configuration in {config_file}: Replacing instances of '{configured_ip}' with '{current_host_ip}'...")
    updated_count = 0
    for prop in root.findall('.//property'):
        name_elem = prop.find('name')
        value_elem = prop.find('value')
        if name_elem is not None and value_elem is not None and name_elem.text in properties_to_update:
            original_value = value_elem.text.strip() if value_elem.text else ''
            # Thay thế IP cũ bằng IP mới, giữ nguyên phần port và định dạng (hdfs:// nếu có)
            new_value = re.sub(
                r'^(hdfs://)?' + re.escape(configured_ip) + r'((?::\d+)?)$',
                lambda m: f"{m.group(1) or ''}{current_host_ip}{m.group(2) or ''}",
                original_value
            )
            if new_value != original_value:
                print(f"  Updating property '{name_elem.text}': '{original_value}' -> '{new_value}'")
                value_elem.text = new_value
                updated_count += 1

    if updated_count == 0:
        print(f"Weird state in {config_file}: Update was marked as needed, but no properties were actually changed. Check logic.")
        return False

    # --- Ghi lại file XML ---
    try:
        print(f"\nWriting updated configuration back to {config_file}...")
        tree.write(config_file, encoding='utf-8', xml_declaration=True)
        print(f"Configuration file {config_file} updated successfully.")
        return True
    except PermissionError:
        print(f"Error: Permission denied when trying to write to {config_file}. Try running with sudo.")
        return False
    except Exception as e:
        print(f"Error writing updated configuration file {config_file}: {e}")
        return False

def update_hosts_file(current_host_ip):
    """Update /etc/hosts file with current IP for phuc hostname"""
    hosts_file = "/etc/hosts"
    hostname = "phuc"
    print(f"\nChecking hosts file for {hostname} entry...")
    
    # Read current hosts file
    with open(hosts_file, 'r') as f:
        lines = f.readlines()
    
    # Search for existing entry
    found = False
    new_lines = []
    for line in lines:
        if not line.strip() or line.strip().startswith('#'):
            new_lines.append(line)
            continue
            
        parts = line.strip().split()
        if len(parts) >= 2 and hostname in parts[1:]:
            # Found existing hostname entry
            if parts[0] != current_host_ip:
                # Update IP address
                new_lines.append(f"{current_host_ip} {' '.join(parts[1:])}\n")
                print(f"Updating {hostname} entry: {parts[0]} -> {current_host_ip}")
            else:
                new_lines.append(line)
                print(f"Entry for {hostname} already has correct IP: {current_host_ip}")
            found = True
        else:
            new_lines.append(line)
    
    # Add new entry if not found
    if not found:
        new_lines.append(f"{current_host_ip} {hostname}\n")
        print(f"Adding new entry: {current_host_ip} {hostname}")
    
    # Write changes back
    with open(hosts_file, 'w') as f:
        f.writelines(new_lines)
    
    return True

def run_hdfs_command(command_path):
    """Chạy lệnh HDFS và in output."""
    if not os.path.exists(command_path):
        print(f"Error: Command not found at {command_path}")
        return False
    print(f"Executing: {command_path}")
    try:
        result = subprocess.run([command_path], capture_output=True, text=True, check=False, encoding='utf-8')
        print("-" * 20 + f" Output for {os.path.basename(command_path)} " + "-" * 20)
        print(result.stdout)
        if result.stderr:
            print("-" * 20 + f" Stderr for {os.path.basename(command_path)} " + "-" * 20)
            print(result.stderr)
        print("-" * (60 + len(os.path.basename(command_path))))
        if result.returncode != 0:
            print(f"Warning: {os.path.basename(command_path)} exited with code {result.returncode}.")
            return False
        return True
    except PermissionError:
        print(f"Error: Permission denied when trying to execute {command_path}. Try running with sudo.")
        return False
    except Exception as e:
        print(f"An error occurred while executing {command_path}: {e}")
        return False

# --- Luồng thực thi chính ---
if __name__ == "__main__":
    print("--- HDFS IP Configuration Dynamic Updater ---")

    current_host_ip = get_current_ip(NETWORK_INTERFACE)

    if not current_host_ip:
        print("Failed to determine current host IP. Exiting.")
        sys.exit(1)

    # Cập nhật hdfs-site.xml
    hdfs_updated = update_config_file_dynamically(current_host_ip, HDFS_SITE_FILE, HDFS_PROPERTIES_TO_UPDATE)
    
    # Cập nhật /etc/hosts
    hosts_updated = update_hosts_file(current_host_ip)
    
    # Cập nhật core-site.xml
    # core_updated = update_config_file_dynamically(current_host_ip, CORE_SITE_FILE, CORE_PROPERTIES_TO_UPDATE)

    if hdfs_updated or hosts_updated:  # or core_updated:
        print("\nConfiguration files updated. You may need to restart HDFS services for changes to take effect.")
    else:
        print("\nNo configuration updates were necessary.")