"""Prepare a lossless handoff bundle. This module has no HTTP write path."""
import copy
from .policy import VERSION, holds
from .records import fingerprint


def envelope(pack, receipt):
    items = []
    for item in pack.get('items') or []:
        identifier = item.get('item_id') or item.get('creative_id') or 'item-' + fingerprint(item)[:20]
        items.append({**copy.deepcopy(item), 'item_id': identifier,
                      'holds': holds(item), 'readiness': 'held' if holds(item) else 'ready'})
    return {'contract_version': 2, 'engine_product': 'fulltime', 'product_slug': 'full-time',
            'venture': 'full_time', 'policy_version': VERSION,
            'report_id': receipt['id'], 'revision': receipt['digest'],
            'delivery': {'status': 'pending_handoff', 'write_attempted': False},
            'pack': {**copy.deepcopy(pack), 'items': items},
            'required_capabilities': ['product_isolation', 'stable_item_ids', 'holds',
                                      'provenance', 'typed_metrics', 'publication_receipts']}


def verify_receipt(bundle, receipt):
    """For the future integrator: GET success alone can never acknowledge a report."""
    if not isinstance(receipt, dict) or receipt.get('ok') is not True:
        return False
    stored = receipt.get('report') or {}
    return (stored.get('report_id') == bundle['report_id']
            and stored.get('revision') == bundle['revision']
            and stored.get('product_slug') == bundle['product_slug']
            and stored.get('venture') == bundle['venture']
            and stored.get('pack') == bundle['pack'])
