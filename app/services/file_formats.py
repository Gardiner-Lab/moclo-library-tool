"""
The sequence file formats MoClo reads and writes: GenBank, and SnapGene (.dna).

MoClo's parsers and exporters work in GenBank. A SnapGene file is converted
to GenBank as it arrives, and GenBank to SnapGene as it leaves, so none of
them needed to change (see app/services/snapgene.py).
"""

from io import BytesIO

from flask import request, send_file

from app.services import snapgene

# What an upload may be.
UPLOAD_EXTENSIONS = ('.gb', '.gbk', '.genbank', '.dna')
UPLOAD_DESCRIPTION = 'a GenBank (.gb, .gbk, .genbank) or SnapGene (.dna) file'


def accepted(filename: str) -> bool:
    return (filename or '').lower().endswith(UPLOAD_EXTENSIONS)


def uploaded_genbank(file) -> str:
    """
    An uploaded file's contents as GenBank text, converting a SnapGene file.
    Raises ValueError, with a message for the user, for anything else.
    """
    data = file.read()
    if snapgene.is_snapgene(data, file.filename):
        name = (file.filename or 'Untitled').rsplit('/', 1)[-1].rsplit('.', 1)[0]
        try:
            return snapgene.to_genbank(data, name)
        except Exception as exc:
            raise ValueError(f'Could not read the SnapGene file: {exc}') from exc
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('A GenBank file must be UTF-8 encoded text') from exc


def genbank_download(genbank_text: str, name: str):
    """
    A download of something MoClo exports as GenBank: the GenBank file, or a
    SnapGene file made from it when the route was asked for /snapgene.
    """
    base = name.replace(' ', '_').replace('/', '_') or 'sequence'
    if request.path.rstrip('/').endswith('/snapgene'):
        return send_file(BytesIO(snapgene.from_genbank(genbank_text)), mimetype='application/octet-stream',
                         as_attachment=True, download_name=f'{base}.dna')
    return send_file(BytesIO(genbank_text.encode('utf-8')), mimetype='text/plain',
                     as_attachment=True, download_name=f'{base}.gb')
