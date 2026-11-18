from dataclasses import asdict

from handoff.lookup import ManifestDelivery
from source.format import encode_json


def render_manifest(delivery: ManifestDelivery) -> str:
    manifest = delivery.manifest
    payload = {
        'manifest_id': manifest.manifest_id,
        'evidence_id': manifest.evidence_id,
        'line_id': manifest.line_id,
        'run_id': manifest.run_id,
        'origin': asdict(manifest.origin),
        'receipt': asdict(delivery.receipt),
        'rows': [asdict(row) for row in manifest.rows],
    }
    return encode_json(payload) + '\n'
