from pathlib import Path
import mido
import os
import json

MIDI_NOTE_TO_LANE = {
    60: 0,
    61: 1,
    62: 2,
    63: 3,
    64: 4,
}

def load_chart_from_midi(midi_path: str):
    mid = mido.MidiFile(midi_path)
    tpq = mid.ticks_per_beat

    print("Ticks per beat (tpq):", tpq)

    print("Pistas en el MIDI:")
    for i, track in enumerate(mid.tracks):
        name = ""
        for msg in track:
            if msg.type == "track_name":
                name = msg.name
                break
        print(f"  Track {i}: '{name}'")

    part_track = None
    for track in mid.tracks:
        name = ""
        for msg in track:
            if msg.type == "track_name":
                name = msg.name.lower()
                break
        if "guitar" in name or "part guitar" in name:
            part_track = track
            print("Usando pista:", name)
            break

    if part_track is None:
        print("No se encontró pista de guitarra, usando la pista 0")
        part_track = mid.tracks[0]

    tempo = 500000
    ticks_acc = 0
    chart = []
    used_notes = set()

    for msg in part_track:
        ticks_acc += msg.time
        if msg.type == "set_tempo":
            tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            note = msg.note
            used_notes.add(note)
            if note in MIDI_NOTE_TO_LANE:
                lane = MIDI_NOTE_TO_LANE[note]
                t_sec = mido.tick2second(ticks_acc, tpq, tempo)
                t_ms = int(round(t_sec * 1000))
                chart.append([t_ms, lane])

    print("Notas MIDI distintas encontradas en la pista:", sorted(used_notes))
    print("Total de notas mapeadas a lanes:", len(chart))

    chart.sort(key=lambda x: x[0])
    return chart

def main():
    print("Working directory:", os.getcwd())
    print("Archivos en carpeta:", os.listdir())

    midi_file = Path(__file__).with_name("notes.mid")
    print("Usando archivo:", midi_file)

    chart = load_chart_from_midi(str(midi_file))

    out_file = Path(__file__).with_name("notes.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(chart, f, indent=4)

    print("Primeras 10 notas:", chart[:10])
    print("Últimas 10 notas:", chart[-10:] if chart else [])
    print("Chart completo guardado en:", out_file)

if __name__ == "__main__":
    main()
