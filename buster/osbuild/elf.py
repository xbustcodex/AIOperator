"""Minimal ELF header parsing for architecture verification (stdlib only).

Enough to read, from a binary in the rootfs, the ELF class and machine so the
distribution build can verify that extracted binaries actually match the
target architecture — without executing them.
"""

import struct


class ElfHeader:
    __slots__ = ("e_class", "endian", "e_machine")

    def __init__(self, e_class: int, endian: str, e_machine: int):
        self.e_class = e_class        # EI_CLASS: 1 = 32-bit, 2 = 64-bit
        self.endian = endian          # 'little' | 'big'
        self.e_machine = e_machine    # ELF e_machine

    @property
    def bits(self) -> int:
        return 32 if self.e_class == 1 else 64

    def matches(self, elf_machine: int, elf_class: int) -> bool:
        return self.e_machine == elf_machine and self.e_class == elf_class


MAGIC = b"\x7fELF"


def parse_elf(data: bytes) -> ElfHeader | None:
    if len(data) < 20 or data[:4] != MAGIC:
        return None
    e_class = data[4]
    endian = "big" if data[5] == 2 else "little"
    fmt = ">" if endian == "big" else "<"
    # e_machine is a u16 at file offset 18 for both ELF32 and ELF64.
    e_machine = struct.unpack_from(fmt + "H", data, 18)[0]
    return ElfHeader(e_class=e_class, endian=endian, e_machine=e_machine)