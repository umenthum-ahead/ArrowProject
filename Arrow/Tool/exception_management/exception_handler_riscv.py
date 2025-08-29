"""
RISC-V Exception Handler Implementation

Extends the existing Arrow privilege manager with comprehensive exception testing
capabilities ported from riscv-dv, including mcause/scause-based exception
identification and proper recovery mechanisms.
"""

from typing import List, Dict, Optional, Union
import random

from Arrow.Utils.configuration_management import Configuration
from Arrow.Utils.configuration_management.enums import PrivilegeLevel
from Arrow.Arrow_API.resources.register_manager import RegisterManager_API as RegisterManager
from Arrow.Tool.asm_libraries.asm_logger import AsmLogger
from Arrow.Tool.asm_libraries.label import Label
from Arrow.Tool.asm_libraries.end_test import end_test_asm_convention
from Arrow.Tool.privilege_management.privilege_manager import get_privilege_manager

from .exception_handler import ExceptionHandler
from .exception_types import (
    ExceptionType, CauseCode, PrivilegeMode, CSRAddress, 
    EXCEPTION_CAUSE_MAP, get_csr_address, get_csr_name
)


class RiscVExceptionHandler(ExceptionHandler):
    """
    RISC-V specific exception handler that extends Arrow's existing privilege manager
    with comprehensive exception testing capabilities from riscv-dv.
    """
    
    def __init__(self):
        """Initialize the RISC-V exception handler."""
        super().__init__()
        
        # Validate RISC-V architecture
        self.validate_architecture_support()
        
        # Set supported exceptions for RISC-V
        self.supported_exceptions = [
            ExceptionType.ILLEGAL_INSTRUCTION,
            ExceptionType.INSTRUCTION_ACCESS_FAULT,
            ExceptionType.LOAD_ACCESS_FAULT,
            ExceptionType.STORE_ACCESS_FAULT,
            ExceptionType.ECALL_FROM_UMODE,
            ExceptionType.ECALL_FROM_SMODE,
            ExceptionType.ECALL_FROM_MMODE,
            ExceptionType.BREAKPOINT,
            # Page faults disabled per requirements
            # ExceptionType.INSTRUCTION_PAGE_FAULT,
            # ExceptionType.LOAD_PAGE_FAULT,
            # ExceptionType.STORE_PAGE_FAULT,
        ]
        
        # Get reference to existing privilege manager
        self.privilege_manager = get_privilege_manager()
        
        # Exception handler labels
        self.exception_handler_labels = {}
        self._create_exception_handler_labels()
    
    def _create_exception_handler_labels(self):
        """Create labels for various exception handlers."""
        mode_prefixes = {
            PrivilegeMode.MACHINE: "m",
            PrivilegeMode.SUPERVISOR: "s",
        }
        
        for mode in [PrivilegeMode.MACHINE, PrivilegeMode.SUPERVISOR]:
            prefix = mode_prefixes[mode]
            
            self.exception_handler_labels[mode] = {
                'main_handler': Label(f"{prefix}_exception_handler"),
                'illegal_instr': Label(f"{prefix}_illegal_instr_handler"),
                'instr_fault': Label(f"{prefix}_instr_fault_handler"), 
                'load_fault': Label(f"{prefix}_load_fault_handler"),
                'store_fault': Label(f"{prefix}_store_fault_handler"),
                'ebreak': Label(f"{prefix}_ebreak_handler"),
                'ecall': Label(f"{prefix}_ecall_handler"),
            }
    
    def generate_trap_handler(self, 
                            exception_types: List[ExceptionType],
                            privilege_mode: PrivilegeMode = PrivilegeMode.MACHINE) -> List[str]:
        """
        Generate enhanced trap handler that extends existing privilege manager
        with exception-specific handling logic from riscv-dv.
        
        Args:
            exception_types: List of exception types to handle
            privilege_mode: The privilege mode for the trap handler
            
        Returns:
            List of assembly instruction strings
        """
        # First generate the base privilege manager trap handler
        if privilege_mode == PrivilegeMode.MACHINE:
            priv_level = PrivilegeLevel.RISCV.MACHINE
        elif privilege_mode == PrivilegeMode.SUPERVISOR:
            priv_level = PrivilegeLevel.RISCV.SUPERVISOR
        else:
            raise ValueError(f"Unsupported privilege mode: {privilege_mode}")
        
        # Generate base trap handler
        self.privilege_manager.gen_trap_handler(priv_level)
        
        # Enhance with exception-specific handling
        self._generate_exception_dispatch(privilege_mode, exception_types)
        
        # Generate individual exception handlers
        for exception_type in exception_types:
            self._generate_specific_exception_handler(exception_type, privilege_mode)
        
        return []  # Assembly is generated directly via AsmLogger
    
    def _generate_exception_dispatch(self, 
                                   privilege_mode: PrivilegeMode,
                                   exception_types: List[ExceptionType]):
        """
        Generate the main exception dispatch logic that checks cause codes
        and jumps to appropriate handlers (inspired by riscv-dv).
        """
        mode_prefix = "m" if privilege_mode == PrivilegeMode.MACHINE else "s"
        handler_labels = self.exception_handler_labels[privilege_mode]
        
        # Get CSR addresses for this privilege mode
        cause_csr = get_csr_address(privilege_mode, 'cause')
        epc_csr = get_csr_address(privilege_mode, 'epc')
        
        # Generate main exception handler entry point
        AsmLogger.asm(f".align 2")
        AsmLogger.asm(f"{handler_labels['main_handler']}:")
        
        # Get temporary registers (avoiding stack pointer)
        temp_regs = self._get_temp_registers()
        cause_reg = temp_regs[0]
        temp_reg = temp_regs[1]
        
        # Check if this is an interrupt (MSB set)
        AsmLogger.asm(f"csrr {cause_reg}, 0x{cause_csr:03x}", 
                     comment=f"Read {mode_prefix}cause")
        AsmLogger.asm(f"srli {temp_reg}, {cause_reg}, 63")  # RISC-V 64-bit MSB check
        AsmLogger.asm(f"bnez {temp_reg}, {mode_prefix}_interrupt_handler", 
                     comment="Jump to interrupt handler if MSB set")
        
        # Read EPC for potential instruction analysis
        AsmLogger.asm(f"csrr {temp_reg}, 0x{epc_csr:03x}", 
                     comment=f"Read {mode_prefix}epc")
        
        # Generate cause code checks for each supported exception type
        for exception_type in exception_types:
            if exception_type in EXCEPTION_CAUSE_MAP:
                cause_code = EXCEPTION_CAUSE_MAP[exception_type]
                handler_label = self._get_exception_handler_label(
                    exception_type, privilege_mode
                )
                
                AsmLogger.asm(f"li {temp_reg}, 0x{cause_code:x}", 
                             comment=f"{exception_type.value.upper()}")
                AsmLogger.asm(f"beq {cause_reg}, {temp_reg}, {handler_label}")
        
        # Unhandled exception - fail test
        AsmLogger.asm(f"j test_fail", comment="Unhandled exception")
    
    def _generate_specific_exception_handler(self,
                                           exception_type: ExceptionType,
                                           privilege_mode: PrivilegeMode):
        """Generate handler for a specific exception type."""
        handler_label = self._get_exception_handler_label(exception_type, privilege_mode)
        
        AsmLogger.asm(f"{handler_label}:")
        
        if exception_type == ExceptionType.ILLEGAL_INSTRUCTION:
            self._generate_illegal_instruction_handler(privilege_mode)
        elif exception_type == ExceptionType.INSTRUCTION_ACCESS_FAULT:
            self._generate_access_fault_handler('instruction', privilege_mode)
        elif exception_type == ExceptionType.LOAD_ACCESS_FAULT:
            self._generate_access_fault_handler('load', privilege_mode)
        elif exception_type == ExceptionType.STORE_ACCESS_FAULT:
            self._generate_access_fault_handler('store', privilege_mode)
        elif exception_type == ExceptionType.BREAKPOINT:
            self._generate_breakpoint_handler(privilege_mode)
        elif exception_type in [ExceptionType.ECALL_FROM_UMODE, 
                              ExceptionType.ECALL_FROM_SMODE,
                              ExceptionType.ECALL_FROM_MMODE]:
            # ECALL handling is already implemented in privilege_manager
            AsmLogger.asm(f"j test_pass", comment="ECALL handled by privilege manager")
        else:
            # Default handler - skip instruction and return
            self._generate_skip_instruction_handler(privilege_mode)
    
    def _generate_illegal_instruction_handler(self, privilege_mode: PrivilegeMode):
        """Generate handler for illegal instruction exceptions."""
        AsmLogger.comment("Illegal instruction exception handler")
        
        # Skip the illegal instruction and return
        self._generate_skip_instruction_handler(privilege_mode)
    
    def _generate_access_fault_handler(self, fault_type: str, privilege_mode: PrivilegeMode):
        """
        Generate handler for access fault exceptions.
        
        Args:
            fault_type: 'instruction', 'load', or 'store'
            privilege_mode: The privilege mode
        """
        AsmLogger.comment(f"{fault_type.title()} access fault exception handler")
        
        # For access faults, we need to determine if we can recover
        # This is a simplified version - full PMP recovery would be more complex
        temp_regs = self._get_temp_registers()
        tval_reg = temp_regs[0]
        temp_reg = temp_regs[1]
        
        # Read tval to get faulting address
        tval_csr = get_csr_address(privilege_mode, 'tval')
        AsmLogger.asm(f"csrr {tval_reg}, 0x{tval_csr:03x}", 
                     comment="Read faulting address from tval")
        
        if fault_type == 'instruction':
            # For instruction faults, try to skip the instruction
            self._generate_skip_instruction_handler(privilege_mode)
        else:
            # For load/store faults, skip the instruction
            self._generate_skip_instruction_handler(privilege_mode)
    
    def _generate_breakpoint_handler(self, privilege_mode: PrivilegeMode):
        """Generate handler for breakpoint exceptions."""
        AsmLogger.comment("Breakpoint exception handler")
        
        # Skip the breakpoint instruction and continue
        self._generate_skip_instruction_handler(privilege_mode)
    
    def _generate_skip_instruction_handler(self, privilege_mode: PrivilegeMode):
        """
        Generate code to skip the faulting instruction and return.
        This is the core recovery mechanism from riscv-dv.
        """
        temp_regs = self._get_temp_registers()
        epc_reg = temp_regs[0]
        instr_reg = temp_regs[1]
        
        epc_csr = get_csr_address(privilege_mode, 'epc')
        
        # Read current EPC
        AsmLogger.asm(f"csrr {epc_reg}, 0x{epc_csr:03x}", comment="Read EPC")
        
        # Load instruction at EPC to check if it's compressed
        AsmLogger.asm(f"lw {instr_reg}, 0({epc_reg})", comment="Load instruction")
        
        # Check if instruction is compressed (bits [1:0] != 11)
        AsmLogger.asm(f"andi {instr_reg}, {instr_reg}, 0x3")
        AsmLogger.asm(f"li {temp_regs[2] if len(temp_regs) > 2 else temp_regs[0]}, 0x3")
        AsmLogger.asm(f"beq {instr_reg}, {temp_regs[2] if len(temp_regs) > 2 else temp_regs[0]}, 1f")
        
        # Compressed instruction - advance EPC by 2
        AsmLogger.asm(f"addi {epc_reg}, {epc_reg}, 2", comment="Skip compressed instruction")
        AsmLogger.asm(f"j 2f")
        
        # Uncompressed instruction - advance EPC by 4  
        AsmLogger.asm(f"1:")
        AsmLogger.asm(f"addi {epc_reg}, {epc_reg}, 4", comment="Skip uncompressed instruction")
        
        AsmLogger.asm(f"2:")
        # Write back updated EPC
        AsmLogger.asm(f"csrw 0x{epc_csr:03x}, {epc_reg}", comment="Update EPC")
        
        # Return from exception
        if privilege_mode == PrivilegeMode.MACHINE:
            AsmLogger.asm(f"mret")
        elif privilege_mode == PrivilegeMode.SUPERVISOR:
            AsmLogger.asm(f"sret")
    
    def generate_exception_trigger(self, 
                                 exception_type: ExceptionType,
                                 **kwargs) -> List[str]:
        """
        Generate code that will trigger a specific exception.
        
        Args:
            exception_type: The type of exception to trigger
            **kwargs: Additional parameters specific to the exception type
            
        Returns:
            List of assembly instruction strings that will cause the exception
        """
        instructions = []
        
        if exception_type == ExceptionType.ILLEGAL_INSTRUCTION:
            # Generate illegal instruction
            illegal_opcode = kwargs.get('illegal_opcode', 0x0000000b)  # Illegal opcode
            instructions.append(f".word 0x{illegal_opcode:08x}  # Illegal instruction")
            
        elif exception_type == ExceptionType.BREAKPOINT:
            # Generate breakpoint instruction as data to avoid infinite loops
            instructions.append(".word 0x00100073  # ebreak instruction as data")
            
        elif exception_type in [ExceptionType.ECALL_FROM_UMODE,
                              ExceptionType.ECALL_FROM_SMODE, 
                              ExceptionType.ECALL_FROM_MMODE]:
            # Set magic value for privilege manager's ECALL handling
            magic_val = Configuration.RiscvConfig.ecall_arg_magic_val
            ecall_reg = Configuration.RiscvConfig.ecall_arg_reg
            instructions.extend([
                f"li {ecall_reg}, {magic_val}",
                "ecall"
            ])
            
        elif exception_type in [ExceptionType.INSTRUCTION_ACCESS_FAULT,
                              ExceptionType.LOAD_ACCESS_FAULT,
                              ExceptionType.STORE_ACCESS_FAULT]:
            # These would require PMP setup or other access restriction mechanisms
            # For now, generate a placeholder that would need PMP configuration
            fault_addr = kwargs.get('fault_address', '0x0')
            temp_reg = self._get_temp_registers()[0]
            
            instructions.extend([
                f"li {temp_reg}, {fault_addr}",
            ])
            
            if exception_type == ExceptionType.INSTRUCTION_ACCESS_FAULT:
                instructions.append(f"jr {temp_reg}  # Jump to restricted address")
            elif exception_type == ExceptionType.LOAD_ACCESS_FAULT:
                instructions.append(f"lw {temp_reg}, 0({temp_reg})  # Load from restricted address")
            else:  # STORE_ACCESS_FAULT
                instructions.append(f"sw {temp_reg}, 0({temp_reg})  # Store to restricted address")
        
        return instructions
    
    def get_recovery_instructions(self, 
                                exception_type: ExceptionType,
                                **kwargs) -> List[str]:
        """
        Generate instructions to recover from an exception.
        Recovery is handled by the exception handlers themselves.
        """
        return []  # Recovery is built into the handlers
    
    def _get_exception_handler_label(self, 
                                   exception_type: ExceptionType,
                                   privilege_mode: PrivilegeMode) -> str:
        """Get the handler label for a specific exception type."""
        handler_labels = self.exception_handler_labels[privilege_mode]
        
        if exception_type == ExceptionType.ILLEGAL_INSTRUCTION:
            return handler_labels['illegal_instr']
        elif exception_type == ExceptionType.INSTRUCTION_ACCESS_FAULT:
            return handler_labels['instr_fault']
        elif exception_type == ExceptionType.LOAD_ACCESS_FAULT:
            return handler_labels['load_fault']
        elif exception_type == ExceptionType.STORE_ACCESS_FAULT:
            return handler_labels['store_fault']
        elif exception_type == ExceptionType.BREAKPOINT:
            return handler_labels['ebreak']
        elif exception_type in [ExceptionType.ECALL_FROM_UMODE,
                              ExceptionType.ECALL_FROM_SMODE,
                              ExceptionType.ECALL_FROM_MMODE]:
            return handler_labels['ecall']
        else:
            return handler_labels['main_handler']
    
    def _get_temp_registers(self, count: int = 3) -> List[str]:
        """Get temporary registers for use in exception handlers."""
        # Get available registers, avoiding x0 and stack pointers
        all_regs = RegisterManager.get_free_registers(reg_type="gpr")
        
        # Filter out x0 and stack pointers  
        temp_regs = []
        for reg in all_regs:
            if (reg.name != "x0" and 
                reg.name != Configuration.RiscvConfig.get_privileged_stack_pointer(
                    PrivilegeLevel.RISCV.MACHINE).name and
                reg.name != Configuration.RiscvConfig.get_privileged_stack_pointer(
                    PrivilegeLevel.RISCV.SUPERVISOR).name):
                temp_regs.append(reg.name)
                if len(temp_regs) >= count:
                    break
        
        if len(temp_regs) < count:
            # Fall back to a default set
            defaults = ["x5", "x6", "x7", "x28", "x29", "x30", "x31"]
            for reg_name in defaults:
                if reg_name not in temp_regs:
                    temp_regs.append(reg_name)
                    if len(temp_regs) >= count:
                        break
        
        return temp_regs[:count]
    
    def get_configuration_requirements(self) -> Dict[str, any]:
        """Get configuration requirements for RISC-V exception testing."""
        base_reqs = super().get_configuration_requirements()
        
        riscv_reqs = {
            'architecture': 'riscv',
            'privilege_modes_required': ['machine', 'supervisor'],
            'extensions_required': ['i'],  # Base integer instruction set
            'memory_management': 'bare',  # No paging per requirements
            'csr_access': True,
            'trap_handling': True,
        }
        
        base_reqs.update(riscv_reqs)
        return base_reqs
    
    def validate_configuration(self) -> List[str]:
        """Validate RISC-V specific configuration."""
        errors = super().validate_configuration()
        
        # Additional RISC-V specific validation
        if not hasattr(Configuration, 'RiscvConfig'):
            errors.append("RISC-V configuration not available")
        
        return errors