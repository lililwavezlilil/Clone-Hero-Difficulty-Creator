import os
import re
import sys
import tkinter as tk
from tkinter import filedialog

# Enable ANSI colors in standard Windows terminals
os.system('color')

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    DARKGRAY = '\033[90m'
    RESET = '\033[0m'

# --- PARAMETERS ---
FORCE_REPLACE = True
SCAN_ALL_EXPERT = False

# --- BEGIN CLONE HERO DIRECTORY SETUP ---
CONFIG_FILE = "CH_Settings.txt"
songs_directory = None

# 1. Try to read the directory from the config file if it exists
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                songs_directory = line.strip()
                break

# 2. Check if the directory we found actually exists
is_valid_dir = False
if songs_directory and os.path.isdir(songs_directory):
    is_valid_dir = True
    print(f"{Colors.CYAN}Loaded Songs directory from CH_Settings.txt:{Colors.RESET}")
    print(f"{Colors.DARKGRAY}{songs_directory}\n{Colors.RESET}")

# 3. If missing or invalid, prompt the user with a GUI
if not is_valid_dir:
    print(f"{Colors.CYAN}First time setup: Please select your Clone Hero 'songs' folder from the popup window...{Colors.RESET}")
    
    # Hide the root tkinter window
    root = tk.Tk()
    root.withdraw()
    
    # Open folder picker
    songs_directory = filedialog.askdirectory(title="Select your Clone Hero 'songs' folder")
    
    if not songs_directory:
        print(f"\n{Colors.RED}Folder selection cancelled. Exiting.{Colors.RESET}")
        input("Press Enter to exit")
        sys.exit()

    # 4. Generate the config file for Notepad editing later
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write("# Clone Hero Batch-EasyChart Configuration\n")
        f.write("# You can safely edit the path below using Notepad.\n")
        f.write("# Just make sure it points to your actual Clone Hero Songs directory.\n\n")
        f.write(f"{songs_directory}\n")
    
    print(f"\n{Colors.GREEN}Saved! You can change this path anytime by editing {CONFIG_FILE} in Notepad.\n{Colors.RESET}")

# --- END CLONE HERO DIRECTORY SETUP ---

if not os.path.isdir(songs_directory):
    print(f"{Colors.RED}ERROR: Cannot find your Songs folder at {songs_directory}{Colors.RESET}")
    input("Press Enter to exit")
    sys.exit()

print("Clone Hero Difficulty Creator v1.0.1 initialized...\n")
print(f"{Colors.CYAN}Scanning charts in {songs_directory}...{Colors.RESET}")

target_folders = []

# 1. SCAN AND FILTER
for root_dir, _, files in os.walk(songs_directory):
    for file in files:
        if file.endswith('.chart'):
            full_path = os.path.join(root_dir, file)
            
            # Read content, ignoring potential weird encodings, treating as UTF-8
            with open(full_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                content = f.read()
            
            has_expert = re.search(r'\[Expert[A-Za-z]*\]', content)
            has_lower = re.search(r'\[(Hard|Medium|Easy)[A-Za-z]*\]', content)
            
            if has_expert:
                if SCAN_ALL_EXPERT or not has_lower:
                    target_folders.append({
                        'SongName': os.path.basename(root_dir),
                        'ChartFile': full_path
                    })

if not target_folders:
    print(f"{Colors.YELLOW}No matching charts found!{Colors.RESET}")
    input("Press Enter to exit")
    sys.exit()

# 2. GUI SELECTOR
print(f"{Colors.GREEN}Found {len(target_folders)} matching charts.{Colors.RESET}")

def gui_select_charts(charts):
    """Replicates PowerShell's Out-GridView using Tkinter."""
    selected = []
    
    root = tk.Tk()
    root.title("Select Charts to Natively Downchart")
    root.geometry("700x500")
    
    lbl = tk.Label(root, text="Select the charts you want to process (All selected by default):", pady=10)
    lbl.pack()
    
    listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, width=100)
    listbox.pack(padx=20, pady=5, fill=tk.BOTH, expand=True)
    
    for idx, chart in enumerate(charts):
        listbox.insert(tk.END, f"{chart['SongName']}  |  {chart['ChartFile']}")
        listbox.selection_set(idx) # Pre-select everything
        
    def on_confirm():
        for i in listbox.curselection():
            selected.append(charts[i])
        root.destroy()
        
    btn = tk.Button(root, text="Confirm Selection", command=on_confirm, bg='lightgreen', font=('Arial', 10, 'bold'))
    btn.pack(pady=15)
    
    root.mainloop()
    return selected

selected = gui_select_charts(target_folders)

if not selected:
    print(f"{Colors.YELLOW}No charts selected. Exiting.{Colors.RESET}")
    input("Press Enter to exit")
    sys.exit()

# 3. CORE LOGIC FUNCTION
def get_downcharted_notes(notes_data, difficulty, resolution):
    lines = notes_data.split('\n')
    new_lines = []
    
    last_accepted_tick = -99999
    accepted_ticks = {} # Dict storing tick -> list of colors
    
    for line in lines:
        stripped_line = line.strip('\r ')
        
        # Match note line: "  Tick = N Color Length"
        match = re.match(r'^\s*(\d+)\s*=\s*N\s+(\d+)\s+(\d+)', stripped_line)
        if match:
            tick = int(match.group(1))
            color = int(match.group(2))
            length = int(match.group(3))
            
            # Strip HOPO/Strum forces (5 and 6) on lower difficulties
            if color in (5, 6):
                if difficulty == "Hard":
                    new_lines.append(f"  {tick} = N {color} {length}")
                continue
                
            # Normal Frets (0-4) and Open Notes (7)
            if color <= 4 or color == 7:
                
                # COLOR DOWN-MAPPING
                if difficulty == "Medium" and color == 4:
                    color = 3
                if difficulty == "Easy" and color >= 3 and color != 7:
                    color = 2
                    
                # TICK DISTANCE (THINNING OUT FAST SECTIONS)
                if tick not in accepted_ticks:
                    distance = tick - last_accepted_tick
                    skip_tick = False
                    
                    # Easy: Max speed is Quarter Notes (1x Resolution)
                    if difficulty == "Easy" and distance < resolution:
                        skip_tick = True
                    # Medium: Max speed is 8th Notes (0.5x Resolution)
                    if difficulty == "Medium" and distance < (resolution / 2):
                        skip_tick = True
                        
                    if skip_tick:
                        continue # Drop note because it's too fast
                    else:
                        accepted_ticks[tick] = []
                        last_accepted_tick = tick
                        
                # If tick wasn't accepted, drop the note
                if tick not in accepted_ticks:
                    continue
                    
                # CHORD LIMITS
                if color in accepted_ticks[tick]:
                    continue # Prevent duplicate colors
                if difficulty == "Easy" and len(accepted_ticks[tick]) >= 1:
                    continue # Single notes only
                if difficulty == "Medium" and len(accepted_ticks[tick]) >= 2:
                    continue # Max 2-note chords
                    
                accepted_ticks[tick].append(color)
                new_lines.append(f"  {tick} = N {color} {length}")
            else:
                # Keep odd note types intact just in case
                new_lines.append(f"  {tick} = N {color} {length}")
        else:
            # Keep Star Power, Events, and curly braces intact
            if stripped_line != "":
                new_lines.append(stripped_line)
                
    return '\n'.join(new_lines)


# 4. EXECUTE FILE OVERWRITES
for item in selected:
    print(f"{Colors.CYAN}Rewriting: {item['SongName']}...{Colors.RESET}")
    
    with open(item['ChartFile'], 'r', encoding='utf-8-sig', errors='ignore') as f:
        content = f.read()
        
    # Grab song resolution for math (Defaults to 192 if not found)
    resolution = 192
    res_match = re.search(r'(?m)^\s*Resolution\s*=\s*(\d+)', content)
    if res_match:
        resolution = int(res_match.group(1))
        
    # Strip existing Hard/Medium/Easy blocks if ForceReplace is True
    if FORCE_REPLACE:
        content = re.sub(r'(?m)^\[(Hard|Medium|Easy)[A-Za-z]+\]\r?\n\{\r?\n[\s\S]*?\r?\n\}\r?\n?', '', content)
        
    # Find all Expert blocks (Single, DoubleBass, Keys, etc.)
    expert_blocks = re.finditer(r'(?m)^\[Expert([A-Za-z]+)\]\r?\n\{\r?\n([\s\S]*?)\r?\n\}', content)
    
    new_blocks = ""
    
    for match in expert_blocks:
        instrument = match.group(1)
        notes_data = match.group(2)
        
        hard_notes = get_downcharted_notes(notes_data, "Hard", resolution)
        medium_notes = get_downcharted_notes(notes_data, "Medium", resolution)
        easy_notes = get_downcharted_notes(notes_data, "Easy", resolution)
        
        new_blocks += f"\n[Hard{instrument}]\n{{\n{hard_notes}\n}}"
        new_blocks += f"\n[Medium{instrument}]\n{{\n{medium_notes}\n}}"
        new_blocks += f"\n[Easy{instrument}]\n{{\n{easy_notes}\n}}"
        
    # Append the newly generated difficulties to the file
    final_content = content.rstrip() + "\n" + new_blocks + "\n"
    
    # Write back as UTF-8 (without BOM, matching standard Clone Hero formatting)
    with open(item['ChartFile'], 'w', encoding='utf-8') as f:
        f.write(final_content)
        
    print(f"{Colors.GREEN}Success: {item['SongName']} fully downcharted!{Colors.RESET}")

print(f"\n{Colors.MAGENTA}Batch process complete! You can delete EasyChartGenerator.exe.{Colors.RESET}")
input("Press Enter to exit")