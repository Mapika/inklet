"""Typed local table input for versioned figure datasets."""
from collections.abc import Mapping
import csv
import hashlib
import io
import math
from pathlib import Path

from ..core import DiagramError
from .data import Dataset, Source


def read_csv(path, *, types, units=None, name='data', citation=None,
             method='measured', encoding='utf-8-sig', delimiter=','):
    """Read a local CSV into a Dataset with explicit types and source provenance.

    `types` maps selected headers to str, int or float; remaining columns stay
    strings. Headers and row lengths are checked, finite numeric values are
    required, and no rows are dropped or filled. Input is a snapshot: call again
    to read changed bytes. Data edits use the ordinary Dataset.update API.
    """
    if not isinstance(types, Mapping) or any(type(k) is not str or v not in (str,int,float) for k,v in types.items()):
        raise ValueError('types must map column names to str, int or float')
    path=Path(path).resolve()
    payload=path.read_bytes()
    reader=csv.reader(io.StringIO(payload.decode(encoding),newline=''),delimiter=delimiter,strict=True)
    try:
        headers=next(reader,None)
        if not headers or any(not h.strip() for h in headers) or len(set(headers))!=len(headers):
            raise DiagramError('CSV needs nonempty, unique column headers')
        unknown=set(types)-set(headers)
        if unknown:raise DiagramError(f'CSV types name unknown columns: {sorted(unknown)!r}')
        columns={h:[] for h in headers}
        for row in reader:
            if len(row)!=len(headers):
                raise DiagramError(f'CSV line {reader.line_num}: expected {len(headers)} fields, got {len(row)}')
            for header,value in zip(headers,row):
                converter=types.get(header,str)
                try:
                    parsed=converter(value)
                    if converter is float and not math.isfinite(parsed):raise ValueError('non-finite number')
                except ValueError as error:
                    raise DiagramError(f'CSV line {reader.line_num}, column {header!r}: expected finite {converter.__name__}') from error
                columns[header].append(parsed)
    except csv.Error as error:
        raise DiagramError(f'CSV line {reader.line_num}: {error}') from error
    source=Source(path.name if citation is None else citation,method=method)
    # Hash the bytes that were parsed, not a second read that could see an edit.
    object.__setattr__(source,'path',str(path))
    object.__setattr__(source,'sha256',hashlib.sha256(payload).hexdigest())
    return Dataset(columns,units=units,source=source,name=name)
