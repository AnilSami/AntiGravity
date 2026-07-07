# Local Background Music Library

Place your copyright-safe background music tracks here to be mixed into generated Shorts.

## Folder Organization

Organize your music tracks into these emotion-specific subdirectories:

* `uplifting/` — Energetic, triumphant, high-tempo tracks
* `inspirational/` — Motivational, inspiring, uplifting tracks
* `calm/` — Relaxed, soft, peaceful ambient tracks
* `dramatic/` — Tense, urgent, dramatic, suspenseful tracks
* `emotional/` — Melancholic, touching, soft piano/guitar tracks
* `corporate/` — Neutral, business-ready background music
* `default/` — Fallback folder if an emotion folder is empty or unrecognized

## Supported Formats

FFmpeg handles all of these formats natively. You can add tracks ending in:
* `.mp3`
* `.wav`
* `.m4a`
* `.ogg`
* `.flac`

## License Tracking (.json Companion Files)

To keep track of song licenses, place a companion `.json` file with the **exact same name** next to the music file. For example:

### File Structure:
```text
assets/music/uplifting/song1.mp3
assets/music/uplifting/song1.json
```

### JSON Content Example:
```json
{
  "license": "Pixabay Music License",
  "license_id": "12345-ABCDE"
}
```

If no companion JSON is found, the system will set `"license": "Unknown (Locally Placed)"` and `"license_id": null`.

---

## IMPORTANT LEGAL NOTICE
The application will only select files that you place in this library. You must only add music from royalty-free sources or sources whose licenses permit your intended YouTube upload and monetization. The software cannot guarantee copyright safety if unlicensed tracks are added.
