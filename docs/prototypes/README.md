# Prototipi — concept, non codice di produzione

File di riferimento visivo per l'evoluzione "agentica" di WritHer. **Non** vengono
importati dall'app: servono solo a mostrare e discutere la direzione grafica.

## `widget_proto.py`

Prototipo nativo (tkinter + Pillow) del widget agentico: parte come pill compatta
(occhi Pandora + waveform, bordo a gradiente) e in modalità agentica si espande
mostrando il piano, gli step live, una conferma inline con countdown e l'esito
finale.

```
python docs/prototypes/widget_proto.py          # avvia il widget sul desktop
python docs/prototypes/widget_proto.py --dump    # salva i PNG delle fasi
```

Comandi a runtime: `SPAZIO` = ripeti · `ESC` = esci · click su Consenti/Annulla.

### Cosa è già passato in produzione
- La **grafica della pill** (bordo gradiente per-modalità + glow, occhi Pandora
  ingranditi, chromakey magenta) è stata portata su `widget.py`, agganciata alle
  logiche esistenti.
- La **card di conferma** (bordo ambra + countdown) è diventata `agent_panel.py`.

Le fasi restanti (piano multi-step live, log delle azioni + undo, voice mode
hands-free) restano concept da studiare.
