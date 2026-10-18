"""Content-address the actual local image, independently of its config ID.

Docker's image ID is a configuration digest, not an OCI image-manifest
digest. Read the real `docker image save` export without extracting paths.
If the daemon supplies OCI blobs, preserve its exact manifest bytes; legacy
exports are represented by the same config and ordered uncompressed layers.
See https://github.com/opencontainers/image-spec/blob/v1.1.1/manifest.md.
"""
import hashlib
import json
import tarfile


def sha256(raw):
    return "sha256:"+hashlib.sha256(raw).hexdigest()


def manifest_from_export(path, config_digest):
    with tarfile.open(path, "r:") as archive:
        def read(name, limit=1024*1024):
            member=archive.getmember(name)
            if not member.isfile() or member.size>limit:
                raise ValueError("invalid image metadata")
            stream=archive.extractfile(member)
            if stream is None:
                raise ValueError("missing image metadata")
            with stream:
                return stream.read(limit+1)

        names=set(archive.getnames())
        if "index.json" in names:
            # Some Docker exporters retain an OCI index, including optional
            # attestation descriptors. Select only the exact running config.
            def find(descriptor, depth=0):
                if depth>3:
                    raise ValueError("image index nesting exceeds bound")
                digest=descriptor.get("digest", "")
                if not digest.startswith("sha256:") or len(digest)!=71:
                    raise ValueError("invalid image descriptor")
                raw=read("blobs/sha256/"+digest[7:])
                if sha256(raw)!=digest:
                    raise ValueError("image descriptor digest mismatch")
                document=json.loads(raw)
                if document.get("config", {}).get("digest")==config_digest:
                    config=read("blobs/sha256/"+config_digest[7:])
                    if sha256(config)!=config_digest:
                        raise ValueError("image config digest mismatch")
                    return raw
                for child in document.get("manifests", []):
                    result=find(child,depth+1)
                    if result is not None:
                        return result
                return None
            for descriptor in json.loads(read("index.json")).get("manifests", []):
                result=find(descriptor)
                if result is not None:
                    return result
            raise ValueError("export has no manifest for the running image")

        entries=json.loads(read("manifest.json"))
        if len(entries)!=1:
            raise ValueError("export must contain exactly one local image")
        saved=entries[0]
        config=read(saved["Config"])
        if sha256(config)!=config_digest:
            raise ValueError("export differs from the running image config")
        layers=saved["Layers"]
        if not 1<=len(layers)<=128:
            raise ValueError("invalid image layer count")
        descriptors=[]
        for name in layers:
            member=archive.getmember(name)
            if not member.isfile() or member.size>2*1024**3:
                raise ValueError("invalid image layer")
            stream=archive.extractfile(member)
            if stream is None:
                raise ValueError("missing image layer")
            digest=hashlib.sha256()
            with stream:
                while block:=stream.read(1024*1024):
                    digest.update(block)
            descriptors.append({"mediaType":"application/vnd.oci.image.layer.v1.tar",
                "digest":"sha256:"+digest.hexdigest(), "size":member.size})
        # Validate ordered uncompressed layer identities against the running
        # config, so an export cannot substitute another filesystem.
        if json.loads(config).get("rootfs", {}).get("diff_ids") != [d["digest"] for d in descriptors]:
            raise ValueError("image layers disagree with the running config")
        document={"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json",
            "config":{"mediaType":"application/vnd.oci.image.config.v1+json",
                "digest":config_digest,"size":len(config)},"layers":descriptors}
        return json.dumps(document,sort_keys=True,separators=(",", ":")).encode()
