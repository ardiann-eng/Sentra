import os

def move_map_section():
    with open('index.html', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    start_map = -1
    end_map = -1
    start_ai = -1
    end_ai = -1
    
    for i, line in enumerate(lines):
        if '<!-- 5.5 REGIONAL ANALYSIS (HEATMAP) -->' in line:
            start_map = i
        if '<!-- 5. AI STRATEGY & INSIGHTS -->' in line:
            end_map = i - 1
            start_ai = i
        if '<!-- 6. SEASONALITY & NEWS -->' in line:
            end_ai = i - 1
            
    if start_map != -1 and end_map != -1 and start_ai != -1 and end_ai != -1:
        map_section = lines[start_map:end_map + 1]
        ai_section = lines[start_ai:end_ai + 1]
        
        new_lines = lines[:start_map] + ai_section + map_section + lines[end_ai + 1:]
        
        with open('index.html', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print("Successfully moved the Map section below the AI section.")
    else:
        print(f"Could not find sections. Map: {start_map}-{end_map}, AI: {start_ai}-{end_ai}")

if __name__ == '__main__':
    move_map_section()
