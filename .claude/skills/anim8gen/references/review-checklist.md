# Anim8gen Review Checklist

Record a review note before accepting each frame candidate.

Required fields for `review/frame-reviews.json`:

- Frame index and label.
- Candidate path and retry number.
- Pose verdict.
- Identity verdict.
- Camera verdict.
- Hygiene verdict.
- Background and segmentation verdict.
- Decision: accepted, accepted-with-warning, rejected-pose,
  rejected-identity, rejected-background, or rejected-artifact.
- Retry reason or warning notes.

Also mirror the decision into the matching `candidates.jsonl` record as
`reviewStatus`, with a concise `reviewNotes` string. Keep raw generation
metadata such as request ids, refusals, and byte counts separate from review
status.

Reject frames with wrong pose, wrong identity, view drift, extra subjects, text,
watermarks, labels, complex backgrounds, baked effects, or crop/scale problems
that cannot be fixed with alignment metadata.

Use alignment anchors or preview-only offsets only for playback polish. They do
not turn a wrong pose into an accepted source frame.
