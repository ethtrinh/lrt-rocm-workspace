# WheelNext Variant Resolution: How It Works for ROCm

Reference doc consolidating findings on PEP 817 variant resolution,
the variant provider protocol, and how ROCm device packages integrate.
Written to stop re-deriving this from scratch every session.

## The Two-Stage Model

Variant resolution has two distinct stages:

1. **Wheel selection**: The variant provider reports system capabilities.
   The installer uses this to pick which variant wheel to install.
2. **Dep activation**: The installed wheel's own `variant.json` properties
   drive `Requires-Dist` marker evaluation, pulling in conditional deps.

These are separate. The provider doesn't control deps — it only influences
which wheel gets selected. The wheel's metadata controls the dep fan-out.

## Variant Provider Protocol

Providers implement `variantlib.protocols.PluginType`:

```python
class AMDVariantPlugin:
    namespace = "amd"
    is_aot_plugin = False

    @classmethod
    def get_all_configs(cls) -> list[VariantFeatureConfig]:
        # Static: every known GFX target
        return [VariantFeatureConfig(
            name="gfx_arch",
            values=[t.name for t in ALL_TARGETS],
            multi_value=True,
        )]

    @classmethod
    def get_supported_configs(cls) -> list[VariantFeatureConfig]:
        # Dynamic: detected GPUs on this system
        targets = detect_gfx_targets()
        return [VariantFeatureConfig(
            name="gfx_arch",
            values=[t.name for t in targets],
            multi_value=True,
        )] if targets else []
```

**Key points:**
- `get_all_configs()` is constant — same result on any system. Used for
  validation.
- `get_supported_configs()` is dynamic — probes the current system.
  Values ordered by preference (most preferred first).
- `multi_value=True` means a single wheel can declare multiple values
  and matches if ANY declared value appears in the system's supported list.
- Providers run in a **subprocess** (not in-process). uv spawns a Python
  process, communicates via JSON on stdin/stdout.
- Provider reports **leaf targets only** (e.g., `gfx1151`). The hierarchy
  fan-out to device packages is the wheel metadata's job.

## Variant Environment Markers (PEP 817)

PEP 817 introduces four new markers for use in `Requires-Dist`:

| Marker | Type | Example |
|--------|------|---------|
| `variant_namespaces` | `set[str]` | `"amd" in variant_namespaces` |
| `variant_features` | `set[str]` | `"amd :: gfx_arch" in variant_features` |
| `variant_properties` | `set[str]` | `"amd :: gfx_arch :: gfx1151" in variant_properties` |
| `variant_label` | `str` | `variant_label == "rocm63"` |

These are evaluated against the **installed wheel's own `variant.json`**,
not against the provider output. This is the mechanism that activates
the right device package dependencies.

## Variant Wheel Structure

### Filename

```
torch-2.7.0-cp313-cp313-linux_x86_64-rocm_all.whl
                                      ^^^^^^^^^
                                      variant label (1-16 chars)
```

### variant.json (in .dist-info/)

```json
{
  "providers": {
    "amd": {
      "requires": ["rocm-bootstrap>=0.1.0"],
      "plugin-api": "rocm_bootstrap.variant_provider:AMDVariantPlugin",
      "install-time": true,
      "enable-if": "platform_system == 'Linux'"
    }
  },
  "variants": {
    "rocm_all": {
      "amd": {"gfx_arch": ["gfx942", "gfx1100", "gfx1151"]}
    }
  }
}
```

### variants.json (package index level)

Published at `{name}-{version}-variants.json` on the index. Aggregates
all variant entries so uv can select without downloading every wheel.

## How torch + ROCm Device Packages Work

### Setup

- One torch variant wheel covering all built ROCm arches.
- Per-target device wheels at up to 3 hierarchy levels (target,
  sub-family, family), version-locked 1:1 with the host torch version.
- Empty levels are omitted (no package published).

### METADATA Requires-Dist

The kpack wheel rebuilder writes marker-conditioned deps for every
built target, using `rocm_bootstrap.packaging_chain()` to determine
the hierarchy and `device_dist_name()` for the package names:

```
Requires-Dist: torch-device-gfx942==2.7.0; "amd :: gfx_arch :: gfx942" in variant_properties
Requires-Dist: torch-device-gfx9-4==2.7.0; "amd :: gfx_arch :: gfx942" in variant_properties
Requires-Dist: torch-device-gfx9==2.7.0; "amd :: gfx_arch :: gfx942" in variant_properties

Requires-Dist: torch-device-gfx1100==2.7.0; "amd :: gfx_arch :: gfx1100" in variant_properties
Requires-Dist: torch-device-gfx11==2.7.0; "amd :: gfx_arch :: gfx1100" in variant_properties

Requires-Dist: torch-device-gfx1151==2.7.0; "amd :: gfx_arch :: gfx1151" in variant_properties
Requires-Dist: torch-device-gfx11==2.7.0; "amd :: gfx_arch :: gfx1151" in variant_properties
```

Notes:
- `torch-device-gfx11==2.7.0` appears under both gfx1100 and gfx1151.
  pip/uv deduplicates during resolution.
- Empty levels (e.g., gfx11-5 with no sub-family kernels) are simply
  omitted — no dep entry generated.
- Version is pinned `==` because device packages are 1:1 locked with
  the host wheel version.

### Resolution flow

1. uv fetches `torch-2.7.0-variants.json` from the index.
2. uv installs `rocm-bootstrap` into an isolated env (per `providers.amd.requires`).
3. uv invokes the provider subprocess → gets `gfx_arch=["gfx1151"]`.
4. uv matches against variant candidates. The `rocm_all` variant declares
   `gfx_arch: ["gfx942", "gfx1100", "gfx1151"]`. Since `gfx1151` is in
   the list and `multi_value=True`, it matches.
5. uv installs the selected torch wheel.
6. uv evaluates `Requires-Dist` markers against the wheel's variant
   properties. Only deps conditioned on `gfx1151` activate.
7. uv installs `torch-device-gfx1151==2.7.0` and `torch-device-gfx11==2.7.0`.

### Extras (parallel mechanism for non-variant pip)

For users on standard pip without variant support:

```
Provides-Extra: gfx942
Requires-Dist: torch-device-gfx942==2.7.0; extra == "gfx942"
Requires-Dist: torch-device-gfx9-4==2.7.0; extra == "gfx942"
Requires-Dist: torch-device-gfx9==2.7.0; extra == "gfx942"

Provides-Extra: gfx1151
Requires-Dist: torch-device-gfx1151==2.7.0; extra == "gfx1151"
Requires-Dist: torch-device-gfx11==2.7.0; extra == "gfx1151"
```

Then `pip install torch[gfx1151]` works without variant resolution.
Both mechanisms (variant markers and extras) can coexist in the same
METADATA. The variant markers are ignored by non-variant-aware
installers.

## What rocm-bootstrap Provides to the Rebuilder

The kpack wheel rebuilder uses these APIs to generate all metadata:

```python
from rocm_bootstrap import packaging_chain, device_dist_name

for target_name in built_targets:
    chain = packaging_chain(target_name)
    for bundle in chain:
        dist_name = device_dist_name("torch-device", bundle)
        if dist_name in published_packages:
            # Variant marker dep:
            #   Requires-Dist: {dist_name}=={version}; "amd :: gfx_arch :: {target_name}" in variant_properties
            # Extras dep:
            #   Requires-Dist: {dist_name}=={version}; extra == "{target_name}"
```

## Decisions Made

1. **Provider reports leaf targets only.** The hierarchy fan-out is a
   packaging concern handled by the wheel rebuilder at build time.

2. **xnack/ASAN not in package names.** xnack+/- kernels go inside
   arch packages. ASAN is a parallel universe at the index/version level.

3. **Empty hierarchy levels are skipped.** If a sub-family has no
   kernels, no package is published and no dep is generated.

4. **Device packages are version-locked 1:1 with the host wheel.**
   The rebuilder knows the version from the fat wheel it's splitting
   and carries it forward to all device wheels and `==` pins.

## References

- [PEP 817 — Wheel Variants: Beyond Platform Tags](https://peps.python.org/pep-0817/)
- [wheelnext/variantlib](https://github.com/wheelnext/variantlib) — reference implementation
- [wheelnext/amd-variant-provider](https://github.com/wheelnext/amd-variant-provider) — current AMD provider (to be replaced by rocm-bootstrap)
- [uv variant prototype PR #12203](https://github.com/astral-sh/uv/pull/12203)
- [PyPI: rocm-bootstrap](https://pypi.org/project/rocm-bootstrap/)
- `rocm_bootstrap.variant_provider` — our provider implementation
- `rocm_bootstrap.packaging_chain()` — hierarchy lookup for rebuilder
- `rocm_bootstrap.device_dist_name()` — device package name generation
