"""
Trap Handler Generator for Exception Testing

Generates trap handler assembly code that integrates with Arrow's existing
privilege manager while adding comprehensive exception handling capabilities.
"""

from typing import List, Dict, Optional, Set
from enum import Enum

from Arrow.Tool.asm_libraries.asm_logger import AsmLogger
from Arrow.Tool.asm_libraries.label import Label
from Arrow.Utils.configuration_management import Configuration
from Arrow.Utils.configuration_management.enums import PrivilegeLevel
from Arrow.Tool.privilege_management.privilege_manager import get_privilege_manager

from .exception_types import (
    ExceptionType, CauseCode, PrivilegeMode, 
    EXCEPTION_CAUSE_MAP, get_csr_address
)


class TrapVectorMode(Enum):
    """Trap vector modes for RISC-V"""
    DIRECT = 0      # All exceptions and interrupts go to BASE
    VECTORED = 1    # Interrupts go to BASE + 4*cause, exceptions to BASE


class TrapHandlerGenerator:
    """
    Generates comprehensive trap handler code that extends Arrow's existing
    privilege manager with exception-specific handling capabilities.
    """
    
    def __init__(self):
        """Initialize the trap handler generator."""
        self.privilege_manager = get_privilege_manager()
        self.generated_handlers: Set[str] = set()
        
        # Exception handler configuration
        self.vector_mode = TrapVectorMode.DIRECT  # Default to direct mode
        self.exception_recovery_enabled = True
        self.debug_output_enabled = False
        
    def generate_enhanced_trap_handlers(self,
                                      privilege_modes: List[PrivilegeLevel],
                                      exception_types: List[ExceptionType]) -> None:
        """
        Generate enhanced trap handlers that extend the existing privilege manager.
        
        Args:
            privilege_modes: List of privilege levels to generate handlers for
            exception_types: List of exception types to handle
        """
        AsmLogger.comment("=== Enhanced Exception Handler Setup ===")
        
        for priv_level in privilege_modes:
            if not self._is_privilege_level_supported(priv_level):
                continue
                
            # Generate the base trap handler using privilege manager
            self.privilege_manager.gen_trap_handler(priv_level)
            
            # Add exception-specific enhancements
            self._generate_exception_dispatch_enhancement(priv_level, exception_types)
            
            # Generate individual exception handlers
            for exception_type in exception_types:
                self._generate_specific_exception_handler(
                    exception_type, priv_level
                )
    
    def _generate_exception_dispatch_enhancement(self,
                                               privilege_level: PrivilegeLevel,
                                               exception_types: List[ExceptionType]) -> None:
        """
        Generate exception dispatch logic that enhances the existing trap handler.
        This adds the mcause/scause checking logic from riscv-dv.
        """
        mode_char = self._get_mode_character(privilege_level)
        handler_label = f"{mode_char}_enhanced_exception_dispatcher"
        
        if handler_label in self.generated_handlers:
            return
            
        AsmLogger.comment(f"Enhanced exception dispatcher for {privilege_level}")
        AsmLogger.asm(f"{handler_label}:")
        
        # Get CSR addresses for this privilege level
        cause_csr = get_csr_address(
            self._privilege_level_to_mode(privilege_level), 'cause'
        )
        epc_csr = get_csr_address(
            self._privilege_level_to_mode(privilege_level), 'epc'
        )
        tval_csr = get_csr_address(
            self._privilege_level_to_mode(privilege_level), 'tval'
        )
        
        # Use temporary registers (this should coordinate with privilege manager)
        cause_reg = "t0"
        epc_reg = "t1" 
        tval_reg = "t2"
        temp_reg = "t3"
        
        # Read exception information
        AsmLogger.asm(f"csrr {cause_reg}, 0x{cause_csr:03x}", 
                     comment=f"Read {mode_char}cause")
        AsmLogger.asm(f"csrr {epc_reg}, 0x{epc_csr:03x}",
                     comment=f"Read {mode_char}epc") 
        AsmLogger.asm(f"csrr {tval_reg}, 0x{tval_csr:03x}",
                     comment=f"Read {mode_char}tval")
        
        # Check if this is an interrupt (MSB set) - use 64-bit default for RISC-V
        xlen = 64
        AsmLogger.asm(f"srli {temp_reg}, {cause_reg}, {xlen - 1}")
        AsmLogger.asm(f"bnez {temp_reg}, {mode_char}_interrupt_handler",
                     comment="Branch to interrupt handler if MSB set")
        
        # Generate exception cause checks
        for exception_type in exception_types:
            if exception_type in EXCEPTION_CAUSE_MAP:
                self._generate_cause_check(
                    exception_type, cause_reg, temp_reg, privilege_level
                )
        
        # Unhandled exception - could call existing privilege manager failure path
        AsmLogger.asm("j test_fail", comment="Unhandled exception")
        
        self.generated_handlers.add(handler_label)
    
    def _generate_cause_check(self,
                            exception_type: ExceptionType,
                            cause_reg: str,
                            temp_reg: str,
                            privilege_level: PrivilegeLevel) -> None:
        """Generate cause code checking logic for a specific exception type."""
        cause_code = EXCEPTION_CAUSE_MAP[exception_type]
        mode_char = self._get_mode_character(privilege_level)
        handler_label = f"{mode_char}_{exception_type.value}_handler"
        
        AsmLogger.asm(f"li {temp_reg}, 0x{cause_code:x}",
                     comment=f"{exception_type.value.upper()}")
        AsmLogger.asm(f"beq {cause_reg}, {temp_reg}, {handler_label}")
    
    def _generate_specific_exception_handler(self,
                                           exception_type: ExceptionType,
                                           privilege_level: PrivilegeLevel) -> None:
        """Generate handler for a specific exception type."""
        mode_char = self._get_mode_character(privilege_level)
        handler_label = f"{mode_char}_{exception_type.value}_handler"
        
        if handler_label in self.generated_handlers:
            return
            
        AsmLogger.comment(f"Handler for {exception_type.value} in {privilege_level}")
        AsmLogger.asm(f"{handler_label}:")
        
        if exception_type == ExceptionType.ILLEGAL_INSTRUCTION:
            self._generate_illegal_instruction_handler(privilege_level)
        elif exception_type == ExceptionType.INSTRUCTION_ACCESS_FAULT:
            self._generate_access_fault_handler("instruction", privilege_level)
        elif exception_type == ExceptionType.LOAD_ACCESS_FAULT:
            self._generate_access_fault_handler("load", privilege_level)
        elif exception_type == ExceptionType.STORE_ACCESS_FAULT:
            self._generate_access_fault_handler("store", privilege_level)
        elif exception_type == ExceptionType.BREAKPOINT:
            self._generate_breakpoint_handler(privilege_level)
        elif exception_type in [
            ExceptionType.ECALL_FROM_UMODE,
            ExceptionType.ECALL_FROM_SMODE,
            ExceptionType.ECALL_FROM_MMODE
        ]:
            # Delegate to existing privilege manager ECALL handling
            mode_char = self._get_mode_character(privilege_level)
            AsmLogger.asm(f"j {mode_char}_trap_handler",
                         comment="Delegate ECALL to privilege manager")
        else:
            # Default: skip instruction and return
            self._generate_skip_instruction_recovery(privilege_level)
        
        self.generated_handlers.add(handler_label)
    
    def _generate_illegal_instruction_handler(self, privilege_level: PrivilegeLevel) -> None:
        """Generate illegal instruction exception handler."""
        AsmLogger.comment("Illegal instruction handler - skip and continue")
        
        if self.debug_output_enabled:
            # Could add debug output here
            pass
            
        # Skip the illegal instruction
        self._generate_skip_instruction_recovery(privilege_level)
    
    def _generate_access_fault_handler(self, 
                                     fault_type: str, 
                                     privilege_level: PrivilegeLevel) -> None:
        """Generate access fault handler with potential PMP recovery."""
        AsmLogger.comment(f"{fault_type.title()} access fault handler")
        
        # For now, implement basic recovery by skipping instruction
        # Future enhancement: implement PMP recovery logic
        if self.exception_recovery_enabled:
            AsmLogger.comment("TODO: Implement PMP recovery logic")
            
        self._generate_skip_instruction_recovery(privilege_level)
    
    def _generate_breakpoint_handler(self, privilege_level: PrivilegeLevel) -> None:
        """Generate breakpoint exception handler."""
        AsmLogger.comment("Breakpoint handler - skip EBREAK and continue")
        
        # Skip the EBREAK instruction
        self._generate_skip_instruction_recovery(privilege_level)
    
    def _generate_skip_instruction_recovery(self, privilege_level: PrivilegeLevel) -> None:
        """
        Generate instruction skipping recovery logic.
        This handles both compressed and uncompressed instructions.
        """
        epc_csr = get_csr_address(
            self._privilege_level_to_mode(privilege_level), 'epc'
        )
        
        # Registers for recovery
        epc_reg = "t1"
        instr_reg = "t2" 
        temp_reg = "t3"
        
        AsmLogger.comment("Skip faulting instruction recovery")
        
        # Read current EPC
        AsmLogger.asm(f"csrr {epc_reg}, 0x{epc_csr:03x}")
        
        # Load instruction to check if compressed
        AsmLogger.asm(f"lw {instr_reg}, 0({epc_reg})")
        
        # Check if compressed (bits [1:0] != 11)
        AsmLogger.asm(f"andi {temp_reg}, {instr_reg}, 0x3")
        AsmLogger.asm(f"li {instr_reg}, 0x3")
        AsmLogger.asm(f"beq {temp_reg}, {instr_reg}, 1f")
        
        # Compressed instruction - advance by 2
        AsmLogger.asm(f"addi {epc_reg}, {epc_reg}, 2",
                     comment="Skip compressed instruction")
        AsmLogger.asm("j 2f")
        
        # Uncompressed instruction - advance by 4
        AsmLogger.asm("1:")
        AsmLogger.asm(f"addi {epc_reg}, {epc_reg}, 4", 
                     comment="Skip uncompressed instruction")
        
        AsmLogger.asm("2:")
        # Write back updated EPC
        AsmLogger.asm(f"csrw 0x{epc_csr:03x}, {epc_reg}")
        
        # Return from exception
        if privilege_level == PrivilegeLevel.RISCV.MACHINE:
            AsmLogger.asm("mret")
        elif privilege_level == PrivilegeLevel.RISCV.SUPERVISOR:
            AsmLogger.asm("sret")
        else:
            # Should not reach here for user mode
            AsmLogger.asm("j test_fail", comment="Invalid privilege level for return")
    
    def _is_privilege_level_supported(self, privilege_level: PrivilegeLevel) -> bool:
        """Check if a privilege level is supported."""
        return privilege_level in [
            PrivilegeLevel.RISCV.MACHINE,
            PrivilegeLevel.RISCV.SUPERVISOR
        ]
    
    def _get_mode_character(self, privilege_level: PrivilegeLevel) -> str:
        """Get the mode character for a privilege level."""
        if privilege_level == PrivilegeLevel.RISCV.MACHINE:
            return "m"
        elif privilege_level == PrivilegeLevel.RISCV.SUPERVISOR:
            return "s"
        elif privilege_level == PrivilegeLevel.RISCV.USER:
            return "u"
        else:
            raise ValueError(f"Unsupported privilege level: {privilege_level}")
    
    def _privilege_level_to_mode(self, privilege_level: PrivilegeLevel) -> PrivilegeMode:
        """Convert Arrow privilege level to exception management privilege mode."""
        if privilege_level == PrivilegeLevel.RISCV.MACHINE:
            return PrivilegeMode.MACHINE
        elif privilege_level == PrivilegeLevel.RISCV.SUPERVISOR:
            return PrivilegeMode.SUPERVISOR
        elif privilege_level == PrivilegeLevel.RISCV.USER:
            return PrivilegeMode.USER
        else:
            raise ValueError(f"Cannot convert privilege level: {privilege_level}")
    
    def set_vector_mode(self, mode: TrapVectorMode) -> None:
        """Set the trap vector mode."""
        self.vector_mode = mode
    
    def enable_exception_recovery(self, enable: bool = True) -> None:
        """Enable or disable exception recovery mechanisms."""
        self.exception_recovery_enabled = enable
    
    def enable_debug_output(self, enable: bool = True) -> None:
        """Enable or disable debug output in exception handlers."""
        self.debug_output_enabled = enable
    
    def get_generated_handlers(self) -> List[str]:
        """Get list of generated handler labels."""
        return list(self.generated_handlers)