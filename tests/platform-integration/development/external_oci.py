"""Materialise an OCI image from the actual Docker image archive, never its tag."""
import hashlib
import json
from pathlib import Path
import tarfile


def publish(archive, target, expected_config):
    target=Path(target);blobs=target/'blobs';blobs.mkdir(parents=True,mode=0o700)
    def blob(stream,media):
        temporary=target/'pending';digest=hashlib.sha256();size=0
        with temporary.open('wb') as out:
            for chunk in iter(lambda:stream.read(1024*1024),b''):
                out.write(chunk);digest.update(chunk);size+=len(chunk)
        value=digest.hexdigest();temporary.replace(blobs/value)
        return {'mediaType':media,'digest':'sha256:'+value,'size':size}
    with tarfile.open(archive,'r') as tar:
        manifests=json.load(tar.extractfile('manifest.json'))
        if len(manifests)!=1:raise ValueError('DEV06_OCI_SINGLE_IMAGE_REQUIRED')
        docker=manifests[0]
        config_name=docker['Config'];layers=docker['Layers']
        # Tar members are only read by exact name; nothing is extracted to a
        # caller-selected path. Blob names come solely from content digests.
        raw=tar.extractfile(config_name).read();config=json.loads(raw)
        if 'sha256:'+hashlib.sha256(raw).hexdigest()!=expected_config:raise ValueError('DEV06_OCI_CONFIG_MISMATCH')
        import io
        description=blob(io.BytesIO(raw),'application/vnd.oci.image.config.v1+json')
        descriptors=[blob(tar.extractfile(name),'application/vnd.oci.image.layer.v1.tar') for name in layers]
        if [d['digest'] for d in descriptors]!=config['rootfs']['diff_ids']:raise ValueError('DEV06_OCI_LAYER_MISMATCH')
        manifest={'schemaVersion':2,'mediaType':'application/vnd.oci.image.manifest.v1+json','config':description,'layers':descriptors}
        raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(raw).hexdigest()
        (target/'manifest.json').write_bytes(raw)
        (target/'manifest.sha256').write_text(digest)
        return 'sha256:'+digest
