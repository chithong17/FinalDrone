"""Explicit IoU-based internal evaluation; not official referee scoring."""
import json
from collections import Counter
from pathlib import Path

from .tracking import iou


def evaluate(manifest_path, predictions_path, split='dev', threshold=.5):
    if not 0 < threshold <= 1:
        raise ValueError('IoU threshold must be in (0, 1]')
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    predictions = json.loads(Path(predictions_path).read_text(encoding='utf-8'))
    # Predictions: {sample_id: [{bbox, object_type, number, floor, direction}, ...]}.
    counts, by_class = Counter(), {}
    for sample in manifest['samples']:
        if sample['split'] != split:
            continue
        if sample['annotation_status'] != 'reviewed':
            counts['skipped_pending_samples'] += 1
            continue
        counts['reviewed_samples'] += 1
        if sample['sample_id'] not in predictions:
            counts['missing_prediction_samples'] += 1
        truth = sample['objects']
        predicted = predictions.get(sample['sample_id'], [])
        valid_truth = [g for g in truth if not g.get('decoy', False)]
        for obj in valid_truth:
            by_class.setdefault(obj['object_type'], Counter())['ground_truth'] += 1
        for obj in predicted:
            by_class.setdefault(obj.get('object_type') or 'unknown', Counter())['predictions'] += 1
        counts['ground_truth_objects'] += len(valid_truth)
        counts['predicted_objects'] += len(predicted)
        pairs = sorted(((iou(g['bbox'], p['bbox']), i, j) for i, g in enumerate(truth)
                        for j, p in enumerate(predicted)), reverse=True)
        used_truth, used_predicted = set(), set()
        for score, i, j in pairs:
            if score < threshold or i in used_truth or j in used_predicted:
                continue
            used_truth.add(i)
            used_predicted.add(j)
            g, p = truth[i], predicted[j]
            if g.get('decoy', False):
                counts['decoy_predictions'] += 1
                continue
            counts['bbox_matches'] += 1
            kind = g['object_type']
            metrics = by_class.setdefault(kind, Counter())
            metrics['matched_bbox'] += 1
            if p.get('object_type') == kind:
                metrics['correct_class_and_bbox'] += 1
            for field in ('object_type', 'number', 'floor', 'direction'):
                if g.get(field) is not None:
                    counts[field+'_known'] += 1
                    counts[field+'_correct'] += p.get(field) == g[field]
                    counts[field+'_unknown_predictions'] += p.get(field) is None
            if all(g.get(field) is not None for field in ('object_type', 'number', 'floor', 'direction')):
                counts['fully_labeled_matches'] += 1
                counts['complete_correct'] += all(p.get(field) == g[field] for field in ('object_type', 'number', 'floor', 'direction'))
        counts['missed_objects'] += sum(i not in used_truth and not g.get('decoy', False) for i, g in enumerate(truth))
        counts['unmatched_predictions'] += len(predicted)-len(used_predicted)
    if not counts['reviewed_samples']:
        raise ValueError('No reviewed samples in requested split; annotate first')
    return dict(split=split, iou_threshold=threshold,
        note='Internal per-image evaluation. Bbox/decoy needs visual review; this is not physical-object competition scoring.',
        counts=dict(counts), bbox_precision=counts['bbox_matches']/max(1, counts['predicted_objects']),
        bbox_recall=counts['bbox_matches']/max(1, counts['ground_truth_objects']),
        field_accuracy={f: counts[f+'_correct']/counts[f+'_known'] if counts[f+'_known'] else None
                        for f in ('object_type', 'number', 'floor', 'direction')},
        by_class={k: dict(v, precision=v['correct_class_and_bbox']/v['predictions'] if v['predictions'] else None,
                         recall=v['correct_class_and_bbox']/v['ground_truth'] if v['ground_truth'] else None)
                  for k, v in by_class.items()})
