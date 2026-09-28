# Immich CT112 isolated rehearsal — 2026-09-28

> Migration is now complete. See [final cutover handover](IMMICH_CUTOVER_2026-09-28.md) for current state; observations below record preparation stages.

Production remains on UbuntuVM. No cutover has occurred.

MacBookPro is now standalone; see MACBOOKPRO_STANDALONE_2026-09-28.md. CT112 started successfully and its existing NAS bind is explicitly read-only. Docker 29.4.1 and Compose v5.1.3 were already installed. Initial free root-disk space was 29 GiB.

Private rehearsal files are under `/opt/immich-rehearsal` inside CT112. Host staging and rollback material are under `/root/usniverse-immich-preparation-20260928`. Recovery bundles were retrieved again into the user-approved private `/tmp/usniverse-immich-preflight` workstation directory. Temporary workstation files are not durable backup storage.

The rehearsal uses the exact recorded Immich server and ML image digests, PostgreSQL pg14-v0.2.0 and the recorded Redis 6.2 digest. It generates separate database credentials and uses a separate local PostgreSQL data directory. API port 2283 binds only to CT112 loopback; there is no production routing change. The API worker alone runs initially. NAS media is mounted read-only at the original `/usr/src/app/upload` path. `IMMICH_IGNORE_MOUNT_CHECK_ERRORS=true` is a rehearsal-only setting because this version attempts to overwrite mount sentinel files at startup. It MUST NOT be carried into production; normal writable mount checks must pass at cutover. ML is in the optional `ml-test` profile and has not yet been exercised.

Services: `immich-rehearsal-pull.service`, dependent `immich-rehearsal-restore.service`, and independent `immich-rehearsal-readability.service`. These are transient systemd jobs within CT112. The restore verifies the expected backup SHA-256 and refuses an existing public table set before pg_restore. The selected dump SHA-256 is `e3f6cedf0f886b9034bb03edfcf293d85ca99b4791932c8f0417de06a93be949`, matching the verified Sept24 database/original-manifest snapshot. It does not represent a final current cutover snapshot.

Private result files: `restore-complete.json`, `readability.json`, and `restore.log`. Non-secret scripts are in `scripts/immich/`. Image download, restore, readability, API/media validation and memory checks must be confirmed before claiming rehearsal success. No host reboot validation or final single-writer transition has occurred.

## Confirmed results

All four pinned images downloaded successfully. The guarded restore completed without errors: 27,093 assets, 49,840 generated-file records, two users and zero albums. The API is healthy and reports v2.7.5. Three authenticated original downloads matched their database SHA-1 values; temporary API keys were removed from the rehearsal database after each check. Results are in `api-validation.json`.

The inherited ML configuration pointed to `http://192.168.1.219:3003`, which was unreachable from the rehearsal. Only the restored database was changed to `http://immich-machine-learning:3003`, with the inherited value retained in `original-ml-setting.json`. The local ML service is healthy and responds to ping. Synthetic text inference is running as `immich-rehearsal-ml-validation.service`; its result must still be checked. The all-original readability scan is still running and its process I/O counters show continuing progress.

Observed baseline after API startup: server about 428 MiB, database 495 MiB, Redis 4 MiB, ML 237 MiB while initializing; host about 2.7 GiB available. These are not peak workload guarantees. Production routing is not yet identified; the user has been asked for the exact browser/phone Immich URL. Final cutover and host reboot validation remain pending.

Synthetic-text CLIP inference passed with HTTP 200 and a nonempty result. Observed memory after inference: ML about 604 MiB, API 300 MiB, PostgreSQL 387 MiB and Redis 4 MiB. This validates one text-inference workload, not concurrent face detection, video transcoding or large imports.
