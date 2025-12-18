from pathlib import Path
import json

def parse_chart(path, section_name="[ExpertSingle]"):
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()

    resolution = 192
    sync_ticks = []
    in_song = False
    in_sync = False
    in_notes = False
    notes_raw = []

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if s.startswith("[") and s.endswith("]"):
            in_song = (s == "[Song]")
            in_sync = (s == "[SyncTrack]")
            in_notes = (s == section_name)
            continue

        if s == "{":
            continue
        if s == "}":
            in_song = in_sync = in_notes = False
            continue

        if in_song and "=" in s and s.lower().startswith("resolution"):
            parts = s.split("=")
            resolution = int(parts[1].strip())
            continue

        if in_sync and "=" in s:
            left, right = s.split("=", 1)
            tick = int(left.strip())
            parts = right.strip().split()
            if len(parts) >= 2 and parts[0] == "B":
                bpm_raw = int(parts[1])
                bpm = bpm_raw / 1000.0
                sync_ticks.append((tick, bpm))
            continue

        if in_notes and "=" in s:
            left, right = s.split("=", 1)
            tick = int(left.strip())
            parts = right.strip().split()
            if len(parts) >= 3 and parts[0] == "N":
                desc = int(parts[1])
                sustain = int(parts[2])
                notes_raw.append((tick, desc, sustain))

    if not sync_ticks:
        sync_ticks = [(0, 120.0)]

    sync_ticks.sort(key=lambda x: x[0])
    if sync_ticks[0][0] != 0:
        sync_ticks.insert(0, (0, sync_ticks[0][1]))

    segments = []
    current_ms = 0.0
    prev_tick = sync_ticks[0][0]
    prev_bpm = sync_ticks[0][1]
    ms_per_tick_prev = 60000.0 / (prev_bpm * resolution)
    segments.append((prev_tick, current_ms, ms_per_tick_prev))

    for tick, bpm in sync_ticks[1:]:
        delta_ticks = tick - prev_tick
        current_ms += delta_ticks * ms_per_tick_prev
        ms_per_tick = 60000.0 / (bpm * resolution)
        segments.append((tick, current_ms, ms_per_tick))
        prev_tick = tick
        prev_bpm = bpm
        ms_per_tick_prev = ms_per_tick

    def tick_to_ms(tick):
        seg = segments[0]
        for s in segments:
            if s[0] <= tick:
                seg = s
            else:
                break
        tick_start, ms_start, ms_per_tick = seg
        return ms_start + (tick - tick_start) * ms_per_tick

    chart = []
    for tick, desc, sustain in notes_raw:
        if 0 <= desc <= 4:          # solo 5 botones
            t_ms = int(round(tick_to_ms(tick)))
            lane = desc
            chart.append([t_ms, lane])   # OJO: lista, no tupla, para JSON

    chart.sort(key=lambda x: x[0])
    return chart

def main():
    chart_file = Path(__file__).with_name("notes.chart")   # cambia el nombre si es distinto
    chart = parse_chart(chart_file)

    out_path = chart_file.with_name("notes.json")
    out_path.write_text(json.dumps(chart, indent=4), encoding="utf-8")

    print(f"Convertido {chart_file.name} → {out_path.name}")
    print(f"Notas totales: {len(chart)}")

if __name__ == "__main__":
    main()
