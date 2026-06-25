import os
import re
import tkinter as tk
from tkinter import filedialog

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    DARKGRAY = '\033[90m'
    RESET = '\033[0m'

CONFIG_FILE = "CH_Settings.txt"

# ==========================================
# --- DOWNCHARTING RULES & SETTINGS ---
# ==========================================

# --- COLOR RULES ---
# True = Moves Orange notes to Blue. False = Removes Orange notes completely.
MEDIUM_MOVE_ORANGE = True 
# True = Moves Blue/Orange notes to Yellow. False = Removes them completely.
EASY_MOVE_BLUE_ORANGE = True 

# --- RHYTHM SPACING RULES ---
# Controls the minimum distance allowed between notes. 
# 2.0 = Allows fast 8th notes. 1.0 = Limits to slower Quarter notes.
HARD_SPACING_DIVISOR = 2.0   
MEDIUM_SPACING_DIVISOR = 1.5  
EASY_SPACING_DIVISOR = 1.0    

# --- CHORD RULES ---
# Maximum notes allowed to be played at the exact same time.
HARD_MAX_CHORDS = 2
MEDIUM_MAX_CHORDS = 2
EASY_MAX_CHORDS = 1

# ==========================================

def setup_directory():
    songs_directory = None
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    songs_directory = line.strip()
                    break

    is_valid_dir = songs_directory and os.path.isdir(songs_directory)

    if is_valid_dir:
        return songs_directory

    print(f"{Colors.CYAN}First time setup: Please select your Clone Hero songs folder{Colors.RESET}")
    
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    songs_directory = filedialog.askdirectory(title="Please select your Clone Hero songs folder")
    root.destroy()
    
    if not songs_directory:
        print(f"\n{Colors.RED}Folder selection cancelled. Exiting.{Colors.RESET}")
        return None

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write("# Clone Hero Batch-EasyChart Configuration\n")
        f.write("# You can safely edit the path below using Notepad.\n")
        f.write("# Just make sure it points to your actual Clone Hero Songs directory.\n\n")
        f.write(f"{songs_directory}\n")
    
    print(f"\n{Colors.GREEN}Saved! You can change this path anytime by editing {CONFIG_FILE} in Notepad.\n{Colors.RESET}")
    return songs_directory

def gui_select_charts(charts):
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
        listbox.selection_set(idx)
        
    def on_confirm():
        for i in listbox.curselection():
            selected.append(charts[i])
        root.destroy()
        
    btn = tk.Button(root, text="Confirm Selection", command=on_confirm, bg='lightgreen', font=('Arial', 10, 'bold'))
    btn.pack(pady=15)
    
    root.mainloop()
    return selected

def get_downcharted_notes(notes_data, difficulty, resolution):
    lines = notes_data.split('\n')
    new_lines = []
    
    last_accepted_tick = -99999
    accepted_ticks = {} 
    
    for line in lines:
        stripped_line = line.strip('\r ')
        
        match = re.match(r'^\s*(\d+)\s*=\s*N\s+(\d+)\s+(\d+)', stripped_line)
        if match:
            tick = int(match.group(1))
            color = int(match.group(2))
            length = int(match.group(3))
            
            # --- MODIFIER HANDLING (HOPOs and Taps) ---
            if color in (5, 6):
                # Only keep HOPO/Tap modifiers if a base note successfully survived at this exact tick
                if tick in accepted_ticks:
                    new_lines.append(f"  {tick} = N {color} {length}")
                continue
                
            # --- BASE NOTE HANDLING (Green through Orange, plus Open Notes) ---
            if color <= 4 or color == 7:
                # Orange Handling for Medium
                if difficulty == "Medium" and color == 4:
                    if MEDIUM_MOVE_ORANGE:
                        color = 3
                    else:
                        continue 
                        
                # Blue/Orange Handling for Easy
                if difficulty == "Easy" and color >= 3 and color != 7:
                    if EASY_MOVE_BLUE_ORANGE:
                        color = 2
                    else:
                        continue 
                    
                if tick not in accepted_ticks:
                    distance = tick - last_accepted_tick
                    skip_tick = False
                    
                    if difficulty == "Easy" and distance < (resolution / EASY_SPACING_DIVISOR):
                        skip_tick = True
                    if difficulty == "Medium" and distance < (resolution / MEDIUM_SPACING_DIVISOR):
                        skip_tick = True
                    if difficulty == "Hard" and distance < (resolution / HARD_SPACING_DIVISOR):
                        skip_tick = True
                        
                    if skip_tick:
                        continue 
                    else:
                        accepted_ticks[tick] = []
                        last_accepted_tick = tick
                        
                if tick not in accepted_ticks:
                    continue
                    
                if color in accepted_ticks[tick]:
                    continue 
                if difficulty == "Easy" and len(accepted_ticks[tick]) >= EASY_MAX_CHORDS:
                    continue 
                if difficulty == "Medium" and len(accepted_ticks[tick]) >= MEDIUM_MAX_CHORDS:
                    continue 
                if difficulty == "Hard" and len(accepted_ticks[tick]) >= HARD_MAX_CHORDS:
                    continue
                    
                accepted_ticks[tick].append(color)
                new_lines.append(f"  {tick} = N {color} {length}")
            else:
                new_lines.append(f"  {tick} = N {color} {length}")
        else:
            if stripped_line != "":
                new_lines.append(stripped_line)
                
    return '\n'.join(new_lines)

def run():
    print(f"Clone Hero Difficulty Creator v1.2 initialized...\n")
    
    songs_directory = setup_directory()
    if not songs_directory:
        print("\n" + "=" * 46)
        return

    target_folders = []

    for root_dir, _, files in os.walk(songs_directory):
        for file in files:
            if file.endswith('.chart'):
                full_path = os.path.join(root_dir, file)
                
                with open(full_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    content = f.read()
                
                has_expert = re.findall(r'(?m)^\[Expert([A-Za-z]+)\]', content)
                needs_downcharting = False
                
                if has_expert:
                    for instr in has_expert:
                        # Extract blocks (Regex relaxed to catch MIDI converter formatting)
                        h_match = re.search(r'(?m)^\[Hard' + instr + r'\]\s*\{([^}]*)\}', content)
                        m_match = re.search(r'(?m)^\[Medium' + instr + r'\]\s*\{([^}]*)\}', content)
                        e_match = re.search(r'(?m)^\[Easy' + instr + r'\]\s*\{([^}]*)\}', content)
                        
                        # Note checks
                        h_has_notes = h_match and re.search(r'^\s*\d+\s*=\s*N\s+[0-47]', h_match.group(1), re.MULTILINE)
                        
                        m_has_notes = m_match and re.search(r'^\s*\d+\s*=\s*N\s+[0-47]', m_match.group(1), re.MULTILINE)
                        m_has_forbidden = m_match and re.search(r'^\s*\d+\s*=\s*N\s+4\b', m_match.group(1), re.MULTILINE)
                        
                        e_has_notes = e_match and re.search(r'^\s*\d+\s*=\s*N\s+[0-47]', e_match.group(1), re.MULTILINE)
                        e_has_forbidden = e_match and re.search(r'^\s*\d+\s*=\s*N\s+[34]\b', e_match.group(1), re.MULTILINE)
                        
                        # Flag for processing if empty OR if illegal notes are found
                        if not (h_has_notes and m_has_notes and e_has_notes) or m_has_forbidden or e_has_forbidden:
                            needs_downcharting = True
                            break
                            
                if needs_downcharting:
                    target_folders.append({
                        'SongName': os.path.basename(root_dir),
                        'ChartFile': full_path
                    })

    if not target_folders:
        print(f"{Colors.YELLOW}No charts found requiring lower difficulty generation or correction!{Colors.RESET}")
        print("\n" + "=" * 46)
        return

    print(f"{Colors.GREEN}Found {len(target_folders)} charts requiring downcharting or correction.{Colors.RESET}")
    
    selected = gui_select_charts(target_folders)

    if not selected:
        print(f"{Colors.YELLOW}No charts selected. Cancelling process.{Colors.RESET}")
        print("\n" + "=" * 46)
        return

    for item in selected:
        print(f"\n{Colors.CYAN}Evaluating: {item['SongName']}...{Colors.RESET}")
        
        with open(item['ChartFile'], 'r', encoding='utf-8-sig', errors='ignore') as f:
            content = f.read()
            
        resolution = 192
        res_match = re.search(r'(?m)^\s*Resolution\s*=\s*(\d+)', content)
        if res_match:
            resolution = int(res_match.group(1))
            
        expert_blocks = re.finditer(r'(?m)^\[Expert([A-Za-z]+)\][ \t]*\r?\n\{([^}]*)\}', content)
        new_blocks = ""
        
        for match in expert_blocks:
            instrument = match.group(1)
            expert_notes = match.group(2)
            
            # (Regex relaxed to catch MIDI converter formatting)
            h_match = re.search(r'(?m)^\[Hard' + instrument + r'\]\s*\{([^}]*)\}', content)
            m_match = re.search(r'(?m)^\[Medium' + instrument + r'\]\s*\{([^}]*)\}', content)
            e_match = re.search(r'(?m)^\[Easy' + instrument + r'\]\s*\{([^}]*)\}', content)
            
            h_has_notes = h_match and re.search(r'^\s*\d+\s*=\s*N\s+[0-47]', h_match.group(1), re.MULTILINE)
            
            m_has_notes = m_match and re.search(r'^\s*\d+\s*=\s*N\s+[0-47]', m_match.group(1), re.MULTILINE)
            m_has_forbidden = m_match and re.search(r'^\s*\d+\s*=\s*N\s+4\b', m_match.group(1), re.MULTILINE)
            
            e_has_notes = e_match and re.search(r'^\s*\d+\s*=\s*N\s+[0-47]', e_match.group(1), re.MULTILINE)
            e_has_forbidden = e_match and re.search(r'^\s*\d+\s*=\s*N\s+[34]\b', e_match.group(1), re.MULTILINE)

            m_needs_rewrite = not m_has_notes or m_has_forbidden
            e_needs_rewrite = not e_has_notes or e_has_forbidden

            # --- HARD (Source: Expert) ---
            if not h_has_notes:
                print(f"  {Colors.DARKGRAY}[Hard{instrument}] -> Charting from Expert...{Colors.RESET}")
                hard_notes = get_downcharted_notes(expert_notes, "Hard", resolution)
                content = re.sub(r'(?m)^\[Hard' + instrument + r'\][ \t]*\r?\n\{[^}]*\}\r?\n?', '', content)
                new_blocks += f"\n[Hard{instrument}]\n{{\n{hard_notes}\n}}"
                source_for_medium = hard_notes
            else:
                print(f"  {Colors.YELLOW}[Hard{instrument}] -> Skipped (Valid Existing Chart){Colors.RESET}")
                source_for_medium = h_match.group(1)
                
            # --- MEDIUM (Source: Hard) ---
            if m_needs_rewrite:
                reason = "0 notes found" if not m_has_notes else "Forbidden Orange notes detected"
                print(f"  {Colors.DARKGRAY}[Medium{instrument}] -> Rewriting from Hard ({reason})...{Colors.RESET}")
                medium_notes = get_downcharted_notes(source_for_medium, "Medium", resolution)
                content = re.sub(r'(?m)^\[Medium' + instrument + r'\][ \t]*\r?\n\{[^}]*\}\r?\n?', '', content)
                new_blocks += f"\n[Medium{instrument}]\n{{\n{medium_notes}\n}}"
                source_for_easy = medium_notes
            else:
                print(f"  {Colors.YELLOW}[Medium{instrument}] -> Skipped (Valid Existing Chart){Colors.RESET}")
                source_for_easy = m_match.group(1)
                
            # --- EASY (Source: Medium) ---
            if e_needs_rewrite:
                reason = "0 notes found" if not e_has_notes else "Forbidden Blue/Orange notes detected"
                print(f"  {Colors.DARKGRAY}[Easy{instrument}] -> Rewriting from Medium ({reason})...{Colors.RESET}")
                easy_notes = get_downcharted_notes(source_for_easy, "Easy", resolution)
                content = re.sub(r'(?m)^\[Easy' + instrument + r'\][ \t]*\r?\n\{[^}]*\}\r?\n?', '', content)
                new_blocks += f"\n[Easy{instrument}]\n{{\n{easy_notes}\n}}"
            else:
                print(f"  {Colors.YELLOW}[Easy{instrument}] -> Skipped (Valid Existing Chart){Colors.RESET}")
            
        final_content = content.rstrip() + "\n" + new_blocks + "\n"
        
        with open(item['ChartFile'], 'w', encoding='utf-8') as f:
            f.write(final_content)
            
        print(f"{Colors.GREEN}Success: {item['SongName']} processed!{Colors.RESET}")

    print(f"{Colors.MAGENTA}Batch process complete!{Colors.RESET}")
    print("\n" + "=" * 46)

if __name__ == "__main__":
    run()
