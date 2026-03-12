# CLAUDE.md

## Service Description

aspirant-remarkable is a REST microservice for rendering reMarkable Paper Pro notebooks at high-fidelity resolution and managing bidirectional file sync between the device and server. It parses xochitl-format notebooks using rmscene + rmc, renders pages to PNG/PDF via cairosvg, and supports folder browsing, to-device PDF/ePub uploads, and sync status tracking.

This service follows [aspirant-meta conventions](https://github.com/the-anonymous-aspirant/aspirant-meta/blob/main/CONVENTIONS.md) for API contract, logging, testing, and Docker standards.

## How to Run

```bash
# Build the Docker image
docker build -t aspirant-remarkable .

# Run the container (with persistent data volume)
docker run -p 8000:8000 -v remarkabledata:/data/remarkable aspirant-remarkable
```

## How to Test

```bash
# Install test dependencies (tests mock rendering libraries)
pip install -r requirements-test.txt

# Run tests
pytest tests/ -v
```

## Port

The service listens on port **8000** inside the container.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check with dependency status |
| GET | `/setup/ssh-key` | Get public SSH key for device setup |
| POST | `/sync` | Trigger rsync pull from reMarkable |
| GET | `/sync/status` | Last sync info, device IP, battery |
| POST | `/sync/device-info` | Accept device push info (IP, battery) |
| GET | `/notebooks` | List all notebooks (optional `parent_id` filter) |
| GET | `/notebooks/:id` | Get notebook details with page list |
| GET | `/notebooks/:id/pages/:page/render` | Render a page (format: png/pdf, dpi: 150-1200) |
| GET | `/notebooks/:id/export` | Export notebook as PDF or ZIP of PNGs |
| GET | `/folders` | List all folders |
| GET | `/folders/:id/contents` | List items in a folder |
| GET | `/tree` | Full nested folder hierarchy |
| POST | `/to-device/upload` | Upload PDF/ePub to stage for device sync |
| GET | `/to-device/pending` | List files pending sync to device |
| DELETE | `/to-device/:id` | Remove a pending upload |

## Key Architecture Details

- **Rendering pipeline**: rmscene (parse .rm v6) → rmc (strokes to SVG) → cairosvg (SVG to PNG/PDF)
- **Folder hierarchy**: Parses xochitl metadata to build nested folder trees with parent references
- **Bidirectional sync**: rsync pull from device, staging area (`/data/remarkable/to-device/`) for push back
- **SSH key management**: Auto-generates ed25519 keypair on first startup, persisted on data volume
- **To-device uploads**: Generates xochitl-compatible metadata (`.metadata`, `.content`) so the device discovers new files

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `REMARKABLE_HOST` | `10.11.99.1` | reMarkable device IP (USB default) |
| `DATA_PATH` | `/data/remarkable` | Volume mount path for synced notebooks |
