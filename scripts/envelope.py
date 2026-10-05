"""Functional task envelope: an immutable, hash-anchored, machine-checked handoff record.

An ``Envelope`` carries the user's ``root_request`` (pinned by a sha256 ``root_hash``),
an append-only ``ledger`` of events, and ``artifacts`` passed strictly by reference
(paths, SHAs, symbols - never inlined file bodies). Every mutation returns a NEW
envelope. Bots declare ``requires``/``provides`` contracts in registry.yaml and
``validate_hop`` checks them.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from . import sanitize as _sanitize
except ImportError:  # bare-script path
    import sanitize as _sanitize  # type: ignore

SEEDED_FIELDS = ("root_request", "ledger")  # always present on any envelope
RESERVED_NAMES = frozenset(SEEDED_FIELDS) | {"root_hash", "artifacts"}
MAX_ROOT_REQUEST = 20000
MAX_EVENT_VALUE = 2000
MAX_EVENT_KEYS = 16
MAX_LEDGER = 10000
MAX_REF = 300
MAX_REF_LIST = 200
MAX_ENVELOPE_BYTES = 32 * 1024 * 1024
DEFAULT_CONTRACT_REQUIRES = ("root_request", "ledger")

_ANSI_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")
_CTRL_RE = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u2028\u2029\u202a-\u202e\u2066-\u2069\u200b-\u200f]")  # refs are ASCII-only (_REF_RE) anyway
_NAME_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_KEY_RE = re.compile(r"[a-z][a-z0-9_]{0,31}")
# paths, SHAs, ranges, symbols (Foo::bar, a/b.py#L10, HEAD~1..HEAD); no code punctuation
_REF_RE = re.compile(r"[A-Za-z0-9_@./:+~#\\\-\[\]]+")
_URL_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://")
_ABS_RE = re.compile(r"[/\\]|[A-Za-z]:[/\\]")
# `file:x`, `x:y`, `javascript:...` (dotted module refs like pkg.mod:Class and `Foo::bar` symbols stay valid)
_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*:(?!:)")
_PROTECTED_PREFIXES = (".capsule", ".git")


class EnvelopeError(ValueError):
    """Envelope integrity, sanitization, or contract failure."""


class HopError(EnvelopeError):
    """A bot's required inputs are missing from the envelope."""

    def __init__(self, bot: str, missing: Sequence[str]):
        self.bot = bot
        self.missing = tuple(missing)
        super().__init__(f"hop '{bot}' missing required inputs: {', '.join(self.missing)}")


def sanitize_text(value: Any, limit: Optional[int] = None, keep_newlines: bool = False) -> str:
    """Thin wrapper over the shared scripts/sanitize.py: strips ANSI, controls and invisible/format chars."""
    return _sanitize.cap(_sanitize.scrub(value, keep_newlines), limit)


def hash_root(root_request: str) -> str:
    return hashlib.sha256(root_request.encode("utf-8")).hexdigest()


def check_ref(name: str, ref: Any) -> Any:
    """Validate one artifact value: a reference string, or a tuple of reference strings."""
    if isinstance(ref, (list, tuple)):
        if not ref or len(ref) > MAX_REF_LIST:
            raise EnvelopeError(f"artifact '{name}' must hold 1-{MAX_REF_LIST} references")
        return tuple(check_ref(name, item) for item in ref)
    if not isinstance(ref, str):
        raise EnvelopeError(f"artifact '{name}' must be a string reference")
    if len(ref) > MAX_REF:
        raise EnvelopeError(f"artifact '{name}' exceeds {MAX_REF} chars; pass a reference, not file contents")
    if not ref.strip() or ref != ref.strip():
        raise EnvelopeError(f"artifact '{name}' is empty or has surrounding whitespace")
    if "\n" in ref or "\r" in ref or _CTRL_RE.search(ref) or _ANSI_RE.search(ref):
        raise EnvelopeError(f"artifact '{name}' contains newlines/control characters; pass a reference, not file contents")
    if not _REF_RE.fullmatch(ref):
        raise EnvelopeError(f"artifact '{name}' does not look like a path, SHA, or symbol reference")
    if _URL_SCHEME_RE.match(ref) or _ABS_RE.match(ref) or ".." in re.split(r"[/\\]", ref):
        raise EnvelopeError(f"artifact '{name}' must be a relative reference without '..' segments, URL schemes, or absolute paths")
    segs = re.split(r"[/\\]", ref)
    if ref.startswith("~") or _SCHEME_RE.match(ref) or "." in segs[1:]:
        raise EnvelopeError(f"artifact '{name}' must not start with '~', use a URL/file scheme, or contain '.' path segments")
    first = next((s_ for s_ in segs if s_ != "."), "").lower()
    if first in _PROTECTED_PREFIXES:
        raise EnvelopeError(f"artifact '{name}' must not point into .capsule/ or .git/")
    return ref


def _norm_event(event: Any) -> Mapping[str, str]:
    if isinstance(event, str):
        event = {"note": event}
    if not isinstance(event, Mapping) or not event:
        raise EnvelopeError("ledger event must be a non-empty string or mapping")
    if len(event) > MAX_EVENT_KEYS:
        raise EnvelopeError(f"ledger event has more than {MAX_EVENT_KEYS} keys")
    out: Dict[str, str] = {}
    for key, val in event.items():
        key = sanitize_text(key).strip().lower()
        if not _KEY_RE.fullmatch(key):
            raise EnvelopeError(f"invalid ledger event key {key!r}")
        out[key] = sanitize_text("" if val is None else val, MAX_EVENT_VALUE)
    return MappingProxyType(out)


def _norm_bot(name: Any) -> str:
    return str(name).strip().lower().replace("_", "-")


class Envelope:
    """Immutable envelope. Use ``Envelope.new(root_request)``; every change returns a new one."""

    __slots__ = ("root_request", "root_hash", "ledger", "artifacts", "legacy_ledger")

    def __init__(self, root_request: str, root_hash: Optional[str] = None,
                 ledger: Iterable[Any] = (), artifacts: Optional[Mapping[str, Any]] = None):
        if not isinstance(root_request, str):
            raise EnvelopeError("root_request must be a string")
        clean = sanitize_text(root_request, keep_newlines=True)
        if not clean.strip():
            raise EnvelopeError("root_request must not be empty")
        if len(clean) > MAX_ROOT_REQUEST:
            raise EnvelopeError(f"root_request exceeds {MAX_ROOT_REQUEST} chars")
        expected = hash_root(clean)
        if root_hash is not None and root_hash != expected:
            raise EnvelopeError("root_hash mismatch: root_request was tampered with or altered")
        events = tuple(_norm_event(e) for e in ledger)
        if len(events) > MAX_LEDGER:
            raise EnvelopeError(f"ledger exceeds {MAX_LEDGER} events")
        arts: Dict[str, Any] = {}
        for name, ref in (artifacts or {}).items():
            if not isinstance(name, str) or not _NAME_RE.fullmatch(name) or name in RESERVED_NAMES:
                raise EnvelopeError(f"invalid artifact name {name!r}")
            arts[name] = check_ref(name, ref)
        set_ = object.__setattr__
        set_(self, "root_request", clean)
        set_(self, "root_hash", expected)
        set_(self, "ledger", events)
        set_(self, "artifacts", MappingProxyType(arts))
        set_(self, "legacy_ledger", False)

    def __setattr__(self, name, value):
        raise AttributeError("Envelope is immutable")

    def __delattr__(self, name):
        raise AttributeError("Envelope is immutable")

    def __eq__(self, other):
        return isinstance(other, Envelope) and self.to_dict() == other.to_dict()

    def __hash__(self):
        return hash((self.root_hash, len(self.ledger), tuple(sorted(self.artifacts))))

    def __repr__(self):
        return f"Envelope(root_hash={self.root_hash[:12]}, ledger={len(self.ledger)}, artifacts={sorted(self.artifacts)})"

    @classmethod
    def new(cls, root_request: str, artifacts: Optional[Mapping[str, Any]] = None) -> "Envelope":
        return cls(root_request, None, (), artifacts)

    def append(self, event: Any) -> "Envelope":
        """Return a new envelope with ``event`` appended to the ledger."""
        return Envelope(self.root_request, self.root_hash, self.ledger + (_norm_event(event),), self.artifacts)

    def with_artifact(self, name: str, ref: Any) -> "Envelope":
        """Return a new envelope with artifact ``name`` set to a reference (never file contents)."""
        arts = dict(self.artifacts)
        arts[name] = ref
        return Envelope(self.root_request, self.root_hash, self.ledger, arts)

    # -- contracts ---------------------------------------------------------
    def available(self) -> frozenset:
        return frozenset(SEEDED_FIELDS) | frozenset(self.artifacts)

    def missing_inputs(self, bot: str, registry: Mapping) -> List[str]:
        have = self.available()
        return [r for r in contract_of(bot, registry)["requires"] if r not in have]

    def validate_hop(self, bot: str, registry: Mapping) -> "Envelope":
        """Raise HopError unless every field the bot requires is present. Returns self."""
        missing = self.missing_inputs(bot, registry)
        if missing:
            raise HopError(bot, missing)
        return self

    def record_hop(self, bot: str, registry: Mapping, outputs: Mapping[str, Any]) -> "Envelope":
        """Validate the hop, check ``outputs`` cover the bot's ``provides``, return the next envelope."""
        self.validate_hop(bot, registry)
        provides = contract_of(bot, registry)["provides"]
        absent = [p for p in provides if p not in outputs]
        if absent:
            raise EnvelopeError(f"hop '{bot}' did not provide: {', '.join(absent)}")
        env = self
        for name in provides:
            env = env.with_artifact(name, outputs[name])
        return env.append({"kind": "hop", "bot": _norm_bot(bot), "provides": ",".join(provides)})

    # -- (de)serialization ---------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_request": self.root_request,
            "root_hash": self.root_hash,
            "ledger": [dict(e) for e in self.ledger],
            "artifacts": {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.artifacts.items()},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Any) -> "Envelope":
        if not isinstance(data, Mapping) or "root_request" not in data or "root_hash" not in data:
            raise EnvelopeError("envelope payload needs root_request and root_hash")
        ledger = data.get("ledger") or []
        if not isinstance(ledger, list):
            raise EnvelopeError("ledger must be a list")
        arts = data.get("artifacts") or {}
        if not isinstance(arts, Mapping):
            raise EnvelopeError("artifacts must be a mapping")
        return cls(data["root_request"], data["root_hash"], ledger, arts)

    @classmethod
    def from_json(cls, text: str) -> "Envelope":
        try:
            return cls.from_dict(json.loads(text))
        except json.JSONDecodeError as exc:
            raise EnvelopeError(f"invalid envelope JSON: {exc.msg}") from exc


# -- registry contracts --------------------------------------------------------
def load_registry(root: Optional[Path] = None) -> Dict:
    try:
        import yaml
    except ImportError as exc:
        raise EnvelopeError("PyYAML is required to read registry contracts") from exc
    base = root or Path(os.environ.get("CAPSULE_RESOURCE_ROOT", Path(__file__).resolve().parent.parent))
    data = yaml.safe_load((Path(base) / "registry.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("bots"), dict):
        raise EnvelopeError("registry.yaml has no bots mapping")
    return data


def _find_bot(bot: str, registry: Mapping) -> Mapping:
    bots = registry.get("bots", registry)
    want = _norm_bot(bot)
    for key, spec in bots.items():
        if isinstance(spec, Mapping) and want in (_norm_bot(key), _norm_bot(spec.get("name", key))):
            return spec
    raise EnvelopeError(f"unknown bot '{sanitize_text(bot, 64)}' in registry")


def _names(value: Any, what: str, bot: str) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) and _NAME_RE.fullmatch(v) for v in value):
        raise EnvelopeError(f"{bot}: {what} must be a list of field names")
    return tuple(value)


def contract_of(bot: str, registry: Mapping) -> Dict[str, Tuple[str, ...]]:
    """Return {'requires': (...), 'provides': (...)} for a bot.

    A bot with no contract (e.g. freshly scaffolded, ``inherit``) requires only the
    seeded fields. The legacy prose string form is rejected so it cannot silently pass.
    """
    spec = _find_bot(bot, registry)
    inp, out = spec.get("input_contract"), spec.get("output_contract")
    requires: Tuple[str, ...] = DEFAULT_CONTRACT_REQUIRES
    provides: Tuple[str, ...] = ()
    if inp is not None:
        if not isinstance(inp, Mapping):
            raise EnvelopeError(f"{bot}: input_contract is legacy prose; use {{requires: [...], description: ...}}")
        requires = _names(inp.get("requires", []), "input_contract.requires", bot)
    if out is not None:
        if not isinstance(out, Mapping):
            raise EnvelopeError(f"{bot}: output_contract is legacy prose; use {{provides: [...], description: ...}}")
        provides = _names(out.get("provides", []), "output_contract.provides", bot)
    return {"requires": requires, "provides": provides}


# -- persistence (append-only JSONL) ------------------------------------------
def envelopes_dir(base: Path) -> Path:
    return Path(base) / ".capsule" / "envelopes"


def _event_hash(prev_hash: str, event: Mapping) -> str:
    canon = json.dumps(dict(event), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + "\n" + canon).encode("utf-8")).hexdigest()


def _chain(root_hash: str, events: Iterable[Mapping]) -> List[str]:
    """Hash of each event in order (chain starts at the root hash)."""
    out: List[str] = []
    prev = root_hash
    for event in events:
        prev = _event_hash(prev, event)
        out.append(prev)
    return out


def _line(obj: Mapping) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True) + "\n"


def _open_append(path: Path):
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    return os.fdopen(os.open(str(path), flags, 0o600), "a", encoding="utf-8")


def _envelope_lock(directory: Path):
    """Exclusive cross-process lock (same primitives as the room lock) on a 0600 lock file; fails closed."""
    try:
        from . import room as _room
    except ImportError:
        import room as _room  # bare-script path
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(str(directory / ".envelopes.lock"), flags, 0o600)
        except OSError as exc:
            raise EnvelopeError(f"cannot open envelope lock safely: {exc}") from exc
        with os.fdopen(fd, "a+") as fh:
            try:
                _room._lock_handle(fh)
            except Exception as exc:
                raise EnvelopeError(f"could not lock envelopes: {exc}") from exc
            try:
                yield
            finally:
                _room._unlock_handle(fh)

    return _cm()


def persist(env: Envelope, base: Path) -> Path:
    """Append the envelope's new events to ``<base>/.capsule/envelopes/<root_hash16>.jsonl``.

    Existing lines are never rewritten; a stored ledger that is not a prefix of
    ``env.ledger`` raises EnvelopeError.
    """
    directory = envelopes_dir(base)
    if directory.is_symlink() or directory.parent.is_symlink():
        raise EnvelopeError("refusing to write envelopes through a symlinked directory")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{env.root_hash[:16]}.jsonl"
    if path.is_symlink():
        raise EnvelopeError("refusing to write through a symlinked envelope file")
    with _envelope_lock(directory):
        return _persist_locked(env, path)


def _persist_locked(env: Envelope, path: Path) -> Path:
    stored = load(path) if path.exists() and path.stat().st_size else None
    if stored is not None:
        if stored.root_hash != env.root_hash or tuple(map(dict, env.ledger[: len(stored.ledger)])) != tuple(map(dict, stored.ledger)):
            raise EnvelopeError("stored ledger is not a prefix of this envelope (ledger is append-only)")
    lines = []
    if stored is None:
        lines.append(_line({"type": "root", "root_request": env.root_request, "root_hash": env.root_hash}))
    hashes = _chain(env.root_hash, env.ledger)
    start = len(stored.ledger) if stored else 0
    for i in range(start, len(env.ledger)):
        lines.append(_line({"type": "event", "event": dict(env.ledger[i]),
                            "prev_hash": hashes[i - 1] if i else env.root_hash, "hash": hashes[i]}))
    done = dict(stored.artifacts) if stored else {}
    for name, ref in env.to_dict()["artifacts"].items():
        if done.get(name) != (tuple(ref) if isinstance(ref, list) else ref):
            lines.append(_line({"type": "artifact", "name": name, "ref": ref}))
    with _open_append(path) as fh:
        fh.write("".join(lines))
    return path


def _read_envelope_bytes(path: Path) -> bytes:
    try:
        from . import room as _room
    except ImportError:
        import room as _room  # bare-script path
    try:
        return _room.safe_read_bytes(path, MAX_ENVELOPE_BYTES)
    except _room.RoomSecurityError as exc:
        raise EnvelopeError(f"refusing to read envelope file: {exc}") from exc
    except OSError as exc:
        raise EnvelopeError(f"cannot read envelope file: {exc}") from exc


def load(path: Path) -> Envelope:
    """Rebuild an envelope from a JSONL file, verifying the root hash and the ledger hash chain.

    The file must be a regular, non-symlink file of at most MAX_ENVELOPE_BYTES. Chain mismatch raises
    EnvelopeError; a file with unhashed (legacy) events loads with ``legacy_ledger = True``.
    """
    path = Path(path)
    if path.is_symlink():
        raise EnvelopeError("refusing to read a symlinked envelope file")
    root = None
    events: List[Mapping] = []
    arts: Dict[str, Any] = {}
    prev = ""
    chained = False
    legacy = False
    try:
        for raw in _read_envelope_bytes(path).decode("utf-8").splitlines():
            if not raw.strip():
                continue
            rec = json.loads(raw)
            kind = rec.get("type") if isinstance(rec, dict) else None
            if kind == "root" and root is None:
                root = rec
                prev = str(rec.get("root_hash"))
            elif kind == "root" and rec == root:
                continue  # exact-duplicate root record (benign); anything else is malformed
            elif kind == "event" and root is not None:
                event = rec["event"]
                expected = _event_hash(prev, event)
                if "hash" in rec or "prev_hash" in rec:
                    if rec.get("prev_hash") != prev or rec.get("hash") != expected:
                        raise EnvelopeError(f"ledger chain broken at event {len(events) + 1}: "
                                            "events were reordered, dropped, forged or edited")
                    chained = True
                elif chained:
                    raise EnvelopeError(f"ledger chain broken at event {len(events) + 1}: unchained event after chained events")
                else:
                    legacy = True
                prev = expected
                events.append(event)
            elif kind == "artifact" and root is not None:
                arts[rec["name"]] = rec["ref"]
            else:
                raise EnvelopeError("malformed envelope record")
    except (json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise EnvelopeError(f"corrupt envelope file: {type(exc).__name__}") from exc
    if root is None:
        raise EnvelopeError("envelope file has no root record")
    env = Envelope(root.get("root_request"), root.get("root_hash"), events, arts)
    object.__setattr__(env, "legacy_ledger", legacy)
    return env
