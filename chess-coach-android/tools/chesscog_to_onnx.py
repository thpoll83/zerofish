#!/usr/bin/env python3
"""Converts Chesscog's pretrained occupancy classifier to ONNX for the app.

Chesscog (Georg Wölflein, MIT licence, https://github.com/georg-wolflein/chesscog) publishes the
classifier as a pickled PyTorch model: a ResNet-18 that reads a 100x100 crop of one square plus
half a square around it, from the board warped to a top-down view, and says empty or occupied.
This script downloads the release, checks its SHA-256, loads it through a stand-in for
Chesscog's model class, and exports it to ONNX with a free batch size and a softmax on the
output, so the app gets the probability that each square holds a piece.

    python3 tools/chesscog_to_onnx.py app/build/generated/chesscog/assets/chesscog_occupancy.onnx

Needs torch, torchvision and onnx (the CPU build of torch is enough), and onnxruntime to cross-check.
"""
import hashlib, io, sys, types, urllib.request, zipfile
from pathlib import Path

URL = "https://github.com/georg-wolflein/chesscog/releases/download/0.1.0/occupancy_classifier.zip"
SHA256 = "c0c5933b7e882abe349b99ba38e7b47b5f706dcf6134d6ca5a2afd556e8abc35"

def main(out: Path):
    import torch, torch.nn as nn
    from torchvision import models
    data = urllib.request.urlopen(URL, timeout=120).read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        sys.exit(f"checksum mismatch for {URL}: {digest}")
    pt = zipfile.ZipFile(io.BytesIO(data)).read("ResNet.pt")

    # the pickle names chesscog.occupancy_classifier.models.ResNet: provide that class
    class ResNet(nn.Module):
        input_size = 100, 100
        pretrained = True
        def __init__(self):
            super().__init__()
            self.model = models.resnet18(weights=None)
            self.model.fc = nn.Linear(self.model.fc.in_features, 2)
        def forward(self, x):
            return self.model(x)
    pkg = types.ModuleType("chesscog"); sub = types.ModuleType("chesscog.occupancy_classifier")
    mod = types.ModuleType("chesscog.occupancy_classifier.models"); mod.ResNet = ResNet
    sys.modules.update({"chesscog": pkg, "chesscog.occupancy_classifier": sub, "chesscog.occupancy_classifier.models": mod})
    net = torch.load(io.BytesIO(pt), map_location="cpu", weights_only=False).eval()

    class Occupied(nn.Module):
        """Probability of "occupied" (class 1) per crop."""
        def __init__(self, inner):
            super().__init__(); self.inner = inner
        def forward(self, x):
            return torch.softmax(self.inner(x), dim=1)[:, 1]
    wrapped = Occupied(net).eval()
    example = torch.randn(4, 3, 100, 100)
    out.parent.mkdir(parents=True, exist_ok=True)
    final, out = out, out.with_suffix(".part")
    kwargs = dict(input_names=["crops"], output_names=["occupied"], dynamic_axes={"crops": {0: "n"}, "occupied": {0: "n"}}, opset_version=17)
    try:
        torch.onnx.export(wrapped, example, str(out), dynamo=False, **kwargs)
    except TypeError:  # older torch without the dynamo switch
        torch.onnx.export(wrapped, example, str(out), **kwargs)
    # the exported model must give what the PyTorch one gives
    try:
        import onnxruntime as ort
        got = ort.InferenceSession(str(out)).run(None, {"crops": example.numpy()})[0]
        want = wrapped(example).detach().numpy()
        err = float(abs(got - want).max())
        if err > 1e-4:
            sys.exit(f"exported model differs from PyTorch by {err}")
        print(f"checked against PyTorch: max difference {err:.2e}")
    except ImportError:
        print("onnxruntime not installed; export not cross-checked")
    out.replace(final)
    print(f"wrote {final} ({final.stat().st_size / 1e6:.1f} MB)")

if __name__ == "__main__":
    main(Path(sys.argv[1]))
