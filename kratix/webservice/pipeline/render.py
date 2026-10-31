from pathlib import Path
import yaml

request = yaml.safe_load(
    Path("/kratix/input/object.yaml").read_text()
)

name = request["metadata"]["name"]
namespace = request["metadata"].get("namespace", "default")
spec = request["spec"]

labels = {"app": name}

deployment = {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "metadata": {"name": name, "namespace": namespace},
    "spec": {
        "replicas": spec.get("replicas", 2),
        "selector": {"matchLabels": labels},
        "template": {
            "metadata": {"labels": labels},
            "spec": {
                "containers": [{
                    "name": "web",
                    "image": spec["image"],
                    "ports": [{"containerPort": 80}]
                }]
            }
        }
    }
}

service = {
    "apiVersion": "v1",
    "kind": "Service",
    "metadata": {
        "name": name,
        "namespace": namespace,
        "annotations": {
            "lab.platform.example.com/hostname": spec["hostname"]
        }
    },
    "spec": {
        "selector": labels,
        "ports": [{"port": 80, "targetPort": 80}]
    }
}

output = Path("/kratix/output")
output.mkdir(parents=True, exist_ok=True)

for filename, manifest in [
    ("deployment.yaml", deployment),
    ("service.yaml", service)
]:
    (output / filename).write_text(
        yaml.safe_dump(manifest, sort_keys=False)
    )

print(f"Generated Deployment and Service: {namespace}/{name}")
