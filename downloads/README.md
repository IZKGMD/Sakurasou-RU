# Sytrus verification project

This folder contains the FL Studio 24 verification project produced by IZKFLP 0.8.0.

- Original file: `IZKFLP-0.8.0-Sytrus-Verification.flp`
- Size: 283,730 bytes
- SHA-256: `147c623c44b4400a99765301633e8e02e589390770e78935cdbf426d71b41b7a`
- Test change: Sytrus channel IID 6, Main Pitch changed from -12 to -11.
- All other channel plugin-state payloads were checked as unchanged before packaging.

The repository stores an XZ-compressed transport copy because the GitHub connector does not accept local binary files directly. The workflow in `.github/workflows/restore-sytrus-verification.yml` restores and verifies the original FLP, then commits it into this folder.

If Actions are disabled, download the `.flp.xz` file and extract it with 7-Zip.
