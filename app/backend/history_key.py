from __future__ import annotations

import ctypes
import os
import secrets
import tempfile
from ctypes import wintypes
from pathlib import Path


_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _dpapi_transform(data: bytes, *, protect: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("El cifrado del historial requiere Windows DPAPI.")

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    transform = (
        crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    )
    transform.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    transform.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    input_buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    input_blob = _DataBlob(
        len(data),
        ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    output_blob = _DataBlob()
    if not transform(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def protect_key(key: bytes) -> bytes:
    return _dpapi_transform(key, protect=True)


def unprotect_key(protected_key: bytes) -> bytes:
    return _dpapi_transform(protected_key, protect=False)


def default_key_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("Windows no proporcionó la ruta LOCALAPPDATA.")
    return Path(local_app_data) / "MiPrimerAgente" / "history-key.dpapi"


def load_or_create_key(key_path: str | Path | None = None) -> bytes:
    path = Path(key_path) if key_path else default_key_path()
    if path.is_file():
        key = unprotect_key(path.read_bytes())
        if len(key) != 32:
            raise RuntimeError("La clave DPAPI del historial tiene un formato inválido.")
        return key

    key = secrets.token_bytes(32)
    protected_key = protect_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as key_file:
            temporary_path = Path(key_file.name)
            key_file.write(protected_key)
            key_file.flush()
            os.fsync(key_file.fileno())

        try:
            os.rename(temporary_path, path)
        except FileExistsError:
            key = unprotect_key(path.read_bytes())
            if len(key) != 32:
                raise RuntimeError(
                    "La clave DPAPI del historial tiene un formato inválido."
                )
        return key
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
