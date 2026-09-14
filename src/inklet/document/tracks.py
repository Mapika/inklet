"""Allocate document layout tracks subject to span constraints."""
from __future__ import annotations

from .errors import LayoutError


def allocate_tracks(count, weights, constraints, available, gap, axis):
    """Solve contiguous span minima, then fit weighted tracks to the page.

    Longest paths between prefix sums give an exact feasibility bound. Dykstra
    projections find the closest feasible allocation to the requested weights,
    including overlapping spans whose minimum widths share the middle track.
    """
    spans={}
    for start,span,required,_ in constraints:
        spans[start,span]=max(spans.get((start,span),0),required-gap*(span-1))
    prefix=[0.]*(count+1)
    ending = {}
    for (start,span),required in spans.items():
        ending.setdefault(start+span,[]).append((start,required))
    for end in range(1,count+1):
        prefix[end]=max([prefix[end-1]]+[prefix[start]+required
                         for start,required in ending.get(end,())])
    minimum=prefix[-1]+gap*(count-1)
    if available is not None and minimum>available+1e-6:
        raise LayoutError(f'{axis} requires at least {minimum:.2f} mm; only {available:.2f} mm is available '
                          f'for cells {", ".join(c[3] for c in constraints)}. Increase the page size or reduce cell minima.')
    total=prefix[-1] if available is None else available-gap*(count-1)
    weight_sum = sum(weights)
    tracks=[total*w/weight_sum for w in weights]
    if all(span == 1 for _, span in spans):
        floors = [max(0., spans.get((index, 1), 0.)) for index in range(count)]
        remaining = max(0., total-sum(floors))
        if remaining == 0:
            return floors
        # Projection onto a simplex with per-track lower bounds. This is
        # exact in O(n log n); ordinary grids need no iterative span solver.
        values = [target-floor for target, floor in zip(tracks, floors)]
        partial = 0.
        threshold = 0.
        for rank, value in enumerate(sorted(values, reverse=True), 1):
            partial += value
            candidate = (partial-remaining)/rank
            if value > candidate:
                threshold = candidate
        return [floor+max(0., value-threshold) for floor, value in zip(floors, values)]
    sets=[(tuple(range(count)),total,True)]
    sets.extend(((index,),0.,False) for index in range(count))
    sets.extend((tuple(range(start,start+span)),required,False) for (start,span),required in spans.items())
    corrections=[0.]*len(sets)
    for _ in range(10000):
        before=tracks[:]
        for index,(indices,required,equality) in enumerate(sets):
            correction=corrections[index]
            current=sum(tracks[j]+correction for j in indices)
            adjustment=(required-current)/len(indices)
            if not equality: adjustment=max(0.,adjustment)
            for j in indices: tracks[j]+=correction+adjustment
            corrections[index]=-adjustment
        if max(abs(a-b) for a,b in zip(before,tracks))<1e-8:
            if (abs(sum(tracks)-total)<1e-6 and min(tracks)>=-1e-6
                    and all(sum(tracks[start:start+span]) >= required-1e-6
                            for (start,span),required in spans.items())):
                return [max(0.,v) for v in tracks]
    raise LayoutError(f'{axis} constraints did not converge; simplify overlapping spans')
