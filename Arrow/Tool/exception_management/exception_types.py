"""
Exception Types and Constants for RISC-V Exception Testing

Defines the various exception types, cause codes, and privilege modes
used in RISC-V exception handling.
"""

from enum import IntEnum, Enum
from typing import Dict, List, Optional


class PrivilegeMode(IntEnum):
    """RISC-V Privilege Modes"""
    USER = 0
    SUPERVISOR = 1
    MACHINE = 3


class ExceptionType(Enum):
    """Types of exceptions that can be tested"""
    ILLEGAL_INSTRUCTION = "illegal_instruction"
    INSTRUCTION_ACCESS_FAULT = "instruction_access_fault"
    LOAD_ACCESS_FAULT = "load_access_fault"
    STORE_ACCESS_FAULT = "store_access_fault"
    ECALL_FROM_UMODE = "ecall_from_umode"
    ECALL_FROM_SMODE = "ecall_from_smode"
    ECALL_FROM_MMODE = "ecall_from_mmode"
    INSTRUCTION_PAGE_FAULT = "instruction_page_fault"
    LOAD_PAGE_FAULT = "load_page_fault"
    STORE_PAGE_FAULT = "store_page_fault"
    BREAKPOINT = "breakpoint"


class CauseCode(IntEnum):
    """RISC-V Exception Cause Codes (from mcause/scause CSR)"""
    
    # Interrupts (MSB = 1)
    # Note: In practice, these would have bit 31/63 set for interrupts
    USER_SOFTWARE_INTERRUPT = 0
    SUPERVISOR_SOFTWARE_INTERRUPT = 1
    MACHINE_SOFTWARE_INTERRUPT = 3
    USER_TIMER_INTERRUPT = 4
    SUPERVISOR_TIMER_INTERRUPT = 5
    MACHINE_TIMER_INTERRUPT = 7
    USER_EXTERNAL_INTERRUPT = 8
    SUPERVISOR_EXTERNAL_INTERRUPT = 9
    MACHINE_EXTERNAL_INTERRUPT = 11
    
    # Exceptions (MSB = 0)
    INSTRUCTION_ADDRESS_MISALIGNED = 0
    INSTRUCTION_ACCESS_FAULT = 1
    ILLEGAL_INSTRUCTION = 2
    BREAKPOINT = 3
    LOAD_ADDRESS_MISALIGNED = 4
    LOAD_ACCESS_FAULT = 5
    STORE_AMO_ADDRESS_MISALIGNED = 6
    STORE_AMO_ACCESS_FAULT = 7
    ECALL_FROM_UMODE = 8
    ECALL_FROM_SMODE = 9
    ECALL_FROM_MMODE = 11
    INSTRUCTION_PAGE_FAULT = 12
    LOAD_PAGE_FAULT = 13
    STORE_AMO_PAGE_FAULT = 15


class CSRAddress(IntEnum):
    """RISC-V CSR Addresses for Exception Handling"""
    
    # Machine-level CSRs
    MSTATUS = 0x300
    MISA = 0x301
    MEDELEG = 0x302
    MIDELEG = 0x303
    MIE = 0x304
    MTVEC = 0x305
    MCOUNTEREN = 0x306
    MSCRATCH = 0x340
    MEPC = 0x341
    MCAUSE = 0x342
    MTVAL = 0x343
    MIP = 0x344
    
    # Supervisor-level CSRs
    SSTATUS = 0x100
    SEDELEG = 0x102
    SIDELEG = 0x103
    SIE = 0x104
    STVEC = 0x105
    SCOUNTEREN = 0x106
    SSCRATCH = 0x140
    SEPC = 0x141
    SCAUSE = 0x142
    STVAL = 0x143
    SIP = 0x144
    
    # User-level CSRs (if N extension is implemented)
    USTATUS = 0x000
    UIE = 0x004
    UTVEC = 0x005
    USCRATCH = 0x040
    UEPC = 0x041
    UCAUSE = 0x042
    UTVAL = 0x043
    UIP = 0x044


class IllegalInstructionType(Enum):
    """Types of illegal instructions to generate"""
    ILLEGAL_OPCODE = "illegal_opcode"
    ILLEGAL_FUNC3 = "illegal_func3"
    ILLEGAL_FUNC7 = "illegal_func7"
    ILLEGAL_COMPRESSED = "illegal_compressed"
    RESERVED_COMPRESSED = "reserved_compressed"
    HINT_INSTRUCTION = "hint_instruction"
    ILLEGAL_SYSTEM = "illegal_system"


class AccessFaultType(Enum):
    """Types of access faults to generate"""
    PMP_INSTRUCTION_FAULT = "pmp_instruction_fault"
    PMP_LOAD_FAULT = "pmp_load_fault"
    PMP_STORE_FAULT = "pmp_store_fault"
    ATOMIC_OPERATION_FAULT = "atomic_operation_fault"


# Exception to cause code mapping
EXCEPTION_CAUSE_MAP: Dict[ExceptionType, CauseCode] = {
    ExceptionType.ILLEGAL_INSTRUCTION: CauseCode.ILLEGAL_INSTRUCTION,
    ExceptionType.INSTRUCTION_ACCESS_FAULT: CauseCode.INSTRUCTION_ACCESS_FAULT,
    ExceptionType.LOAD_ACCESS_FAULT: CauseCode.LOAD_ACCESS_FAULT,
    ExceptionType.STORE_ACCESS_FAULT: CauseCode.STORE_AMO_ACCESS_FAULT,
    ExceptionType.ECALL_FROM_UMODE: CauseCode.ECALL_FROM_UMODE,
    ExceptionType.ECALL_FROM_SMODE: CauseCode.ECALL_FROM_SMODE,
    ExceptionType.ECALL_FROM_MMODE: CauseCode.ECALL_FROM_MMODE,
    ExceptionType.INSTRUCTION_PAGE_FAULT: CauseCode.INSTRUCTION_PAGE_FAULT,
    ExceptionType.LOAD_PAGE_FAULT: CauseCode.LOAD_PAGE_FAULT,
    ExceptionType.STORE_PAGE_FAULT: CauseCode.STORE_AMO_PAGE_FAULT,
    ExceptionType.BREAKPOINT: CauseCode.BREAKPOINT,
}

# CSR addresses for different privilege modes
MODE_CSR_MAP: Dict[PrivilegeMode, Dict[str, CSRAddress]] = {
    PrivilegeMode.MACHINE: {
        'status': CSRAddress.MSTATUS,
        'tvec': CSRAddress.MTVEC,
        'scratch': CSRAddress.MSCRATCH,
        'epc': CSRAddress.MEPC,
        'cause': CSRAddress.MCAUSE,
        'tval': CSRAddress.MTVAL,
        'ie': CSRAddress.MIE,
        'ip': CSRAddress.MIP,
    },
    PrivilegeMode.SUPERVISOR: {
        'status': CSRAddress.SSTATUS,
        'tvec': CSRAddress.STVEC,
        'scratch': CSRAddress.SSCRATCH,
        'epc': CSRAddress.SEPC,
        'cause': CSRAddress.SCAUSE,
        'tval': CSRAddress.STVAL,
        'ie': CSRAddress.SIE,
        'ip': CSRAddress.SIP,
    },
    PrivilegeMode.USER: {
        'status': CSRAddress.USTATUS,
        'tvec': CSRAddress.UTVEC,
        'scratch': CSRAddress.USCRATCH,
        'epc': CSRAddress.UEPC,
        'cause': CSRAddress.UCAUSE,
        'tval': CSRAddress.UTVAL,
        'ie': CSRAddress.UIE,
        'ip': CSRAddress.UIP,
    },
}

# Legal opcodes for RV32I/RV64I
LEGAL_OPCODES: List[int] = [
    0b0000011,  # LOAD
    0b0001111,  # MISC-MEM
    0b0010011,  # OP-IMM
    0b0010111,  # AUIPC
    0b0100011,  # STORE
    0b0110111,  # LUI
    0b1100011,  # BRANCH
    0b0110011,  # OP
    0b1100111,  # JALR
    0b1110011,  # SYSTEM
    0b1101111,  # JAL
]

# Legal compressed opcodes
LEGAL_COMPRESSED_OPCODES: Dict[int, List[int]] = {
    0: [0b000, 0b010, 0b110],  # C0 quadrant
    1: [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],  # C1 quadrant
    2: [0b000, 0b010, 0b100, 0b110],  # C2 quadrant
}


def get_csr_name(mode: PrivilegeMode, csr_type: str) -> Optional[str]:
    """
    Get the CSR name for a given privilege mode and CSR type.
    
    Args:
        mode: The privilege mode
        csr_type: The type of CSR ('cause', 'epc', 'tvec', etc.)
        
    Returns:
        The CSR name string, or None if not found
    """
    if mode not in MODE_CSR_MAP or csr_type not in MODE_CSR_MAP[mode]:
        return None
    
    csr_addr = MODE_CSR_MAP[mode][csr_type]
    return f"{mode.name.lower()}{csr_type}"


def get_csr_address(mode: PrivilegeMode, csr_type: str) -> Optional[int]:
    """
    Get the CSR address for a given privilege mode and CSR type.
    
    Args:
        mode: The privilege mode
        csr_type: The type of CSR ('cause', 'epc', 'tvec', etc.)
        
    Returns:
        The CSR address as an integer, or None if not found
    """
    if mode not in MODE_CSR_MAP or csr_type not in MODE_CSR_MAP[mode]:
        return None
    
    return MODE_CSR_MAP[mode][csr_type].value


def is_interrupt_cause(cause: int) -> bool:
    """
    Check if a cause code represents an interrupt.
    
    Args:
        cause: The cause code value
        
    Returns:
        True if the cause represents an interrupt (MSB set)
    """
    # For 32-bit systems, check bit 31; for 64-bit, check bit 63
    # We'll assume 64-bit for simplicity, but this should be configurable
    return (cause & (1 << 63)) != 0


def get_exception_name(cause: int) -> Optional[str]:
    """
    Get the exception name for a given cause code.
    
    Args:
        cause: The cause code value
        
    Returns:
        The exception name string, or None if not found
    """
    try:
        cause_enum = CauseCode(cause)
        return cause_enum.name
    except ValueError:
        return None