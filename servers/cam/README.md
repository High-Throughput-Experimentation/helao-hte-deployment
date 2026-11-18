# cam

Action server for an Axis IP camera. It starts and cancels an image-stream acquisition (`acquire_image`, `cancel_acquire_image`).

## Vendor software

No vendor software beyond the env files. The camera is read over HTTP (`requests`); it needs a reachable Axis camera serving `/jpg/1/image.jpg`.

## Params

Host-level keys every server accepts: see docs/config-schema.md ("Group conventions for `params:`").

### `cam_server` (`fast:`)

| key | req | type | default | meaning / allowed values | read at |
|---|---|---|---|---|---|
| `axis_ip` | yes | str | none (KeyError if absent) | IP address or hostname of the Axis camera. Images are fetched from `http://<axis_ip>/jpg/1/image.jpg`. | `helao/deploy/hte/servers/cam/axiscam_driver.py:51`, `:53` |

Example:
```yaml
params:
  axis_ip: 192.168.x.x
```

## Outputs

### `acquire_image` (action)

Writes one JPEG per acquisition and queues one row per image; `action_abbr` is `acq_webcam` (`helao/deploy/hte/servers/cam/cam_server.py:62`). `_exec` writes the first image (`helao/deploy/hte/servers/cam/axiscam_driver.py:124`), and `_poll` writes one more per `acquisition_rate` seconds until `duration` has elapsed (`:145`); `duration: 0` runs `_exec` only. A failed fetch in `_poll` ends the action with an error and queues no row. Rows are queued by `helao/hexagon/app/executor_runner.py:110-117` and `:129-136`.

Data file `acq_webcam-<orch_submit_order>.<action_order>.<action_retry>.<action_split>__<n>.jsonl` (+ `.meta.json`), one row per image (`helao/hexagon/adapters/native/data_file.py:172`):

| field | type | structure | unit | meaning | written at |
|---|---|---|---|---|---|
| `epoch_s` | float | scalar per row | s | Unix time of the image (the `_exec` start time for the first image, the `_poll` iteration start for the others) | `helao/deploy/hte/servers/cam/axiscam_driver.py:107` |
| `filename` | str | scalar per row | none | name of the JPEG written for this row | `helao/deploy/hte/servers/cam/axiscam_driver.py:107` |

Files:

| file | format | name pattern | meaning | written at |
|---|---|---|---|---|
| image | JPEG, bytes exactly as returned by the camera, registered with `track_file` type `webcam_image` | `cam_<counter>_<yymmdd>.<HHMMSS>.jpg`; `<counter>` is a 6-digit count from 0, the time is local time of `epoch_s` | one snapshot from `http://<axis_ip>/jpg/1/image.jpg` | `helao/deploy/hte/servers/cam/axiscam_driver.py:103-108` |

No action results.

### `cancel_acquire_image` (action)

No data files or action results.

## Notes

- `AxisCam.acquire_image` saves `resp.content` without checking the HTTP status (`helao/deploy/hte/servers/cam/axiscam_driver.py:52-56`), so an error page returned by the camera is written to a `.jpg` file.
