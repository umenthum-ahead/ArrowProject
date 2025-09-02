"""
PMP Access Fault Ingredient for Exception Testing

Generates PMP (Physical Memory Protection) access faults for instruction fetch,
load, and store operations. Based on riscv-dv PMP exception handling logic.

RISC-V Only: This ingredient is specifically designed for RISC-V architecture.
"""

import random
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from Arrow.Arrow_API import AR
from Arrow.Arrow_API.resources.memory_manager import MemoryManager_API as MemoryManager
from Arrow.Arrow_API.resources.register_manager import RegisterManager_API as RegisterManager
from Arrow.Arrow_API import AR
from Arrow.Utils.configuration_management import Configuration
from Arrow.Tool.exception_management import ExceptionType, AccessFaultType
from Arrow.Tool.asm_libraries.asm_logger import AsmLogger


class PMPAccessType(Enum):
    """PMP access types that can cause faults"""
    READ = "r"
    WRITE = "w" 
    EXECUTE = "x"


class PMPAddressMode(Enum):
    """PMP address matching modes"""
    OFF = 0
    TOR = 1  # Top of Range
    NA4 = 2  # Naturally aligned 4-byte
    NAPOT = 3  # Naturally aligned power of two


@AR.ingredient_decorator
class AccessFaultIngredient(AR.Ingredient):
    """
    Ingredient that generates PMP access faults by setting up restricted
    memory regions and attempting to access them inappropriately.
    """
    
    def __init__(self,
                 fault_type: Optional[AccessFaultType] = None,
                 fault_count: int = 3,
                 setup_pmp: bool = True):
        """
        Initialize the access fault ingredient.
        
        Args:
            fault_type: Specific type of access fault (None for random)
            fault_count: Number of access faults to generate
            setup_pmp: Whether to set up PMP configuration
        """
        # Validate RISC-V architecture
        if not Configuration.Architecture.riscv:
            raise RuntimeError(
                "PMP access fault testing is only supported for RISC-V architecture. "
                f"Current architecture: {Configuration.Architecture.get_current()}"
            )
        
        self.name = "access_fault_ingredient"
        self.fault_type = fault_type
        self.fault_count = fault_count
        self.setup_pmp = setup_pmp
        
        # PMP configuration state
        self.pmp_regions = []
        self.restricted_memory = None
        self.test_registers = []
        
        # CSR addresses for PMP
        self.pmpcfg_csrs = [0x3A0, 0x3A1, 0x3A2, 0x3A3]  # pmpcfg0-3
        self.pmpaddr_base = 0x3B0  # pmpaddr0 base
        
    def init(self):
        """Initialize ingredient resources and set up PMP if enabled."""
        AR.comment(f"Initializing {self.name}")
        
        # Use the fixed PMP hole address set up in test_boot.py
        # Instead of allocating memory, we reference the fixed address
        self.pmp_hole_base_addr = 0x80000000
        self.pmp_hole_size = 0x1000  # 4KB hole
        
        # Reserve registers for testing (no longer need PMP setup registers)
        self.test_registers = [
            RegisterManager.get_and_reserve() for _ in range(3)
        ]
        
        # PMP hole is already set up in test_boot.py, no need to configure here
        AR.comment(f"Using PMP hole at address 0x{self.pmp_hole_base_addr:08x} (size: {self.pmp_hole_size} bytes)")
        
        # Store PMP region info for reference  
        self.pmp_regions.append({
            'base_address': f"0x{self.pmp_hole_base_addr:08x}",
            'size': self.pmp_hole_size,
            'permissions': '',  # No permissions - this is the hole
            'mode': PMPAddressMode.NAPOT
        })
    
    def body(self):
        """Generate access fault test sequences."""
        AR.comment(f"Generating {self.fault_count} access fault tests")
        
        for i in range(self.fault_count):
            fault_type = self.fault_type or self._choose_random_fault_type()
            
            AR.comment(f"Access fault test {i+1}: {fault_type.value}")
            
            if fault_type == AccessFaultType.PMP_INSTRUCTION_FAULT:
                self._generate_instruction_access_fault()
            elif fault_type == AccessFaultType.PMP_LOAD_FAULT:
                self._generate_load_access_fault()
            elif fault_type == AccessFaultType.PMP_STORE_FAULT:
                self._generate_store_access_fault()
            elif fault_type == AccessFaultType.ATOMIC_OPERATION_FAULT:
                self._generate_atomic_access_fault()
            
            # Add some spacing and recovery instructions
            AsmLogger.asm("nop  # Recovery padding")
            
            yield  # Important: yield for proper state management
    
    def final(self):
        """Clean up ingredient resources."""
        AR.comment(f"Finalizing {self.name}")
        
        # Free reserved registers
        for reg in self.test_registers:
            RegisterManager.free(reg)
        
        self.test_registers.clear()
        self.pmp_regions.clear()
    
    
    def _choose_random_fault_type(self) -> AccessFaultType:
        """Choose a random access fault type."""
        fault_types = [
            AccessFaultType.PMP_LOAD_FAULT,
            AccessFaultType.PMP_STORE_FAULT,
            AccessFaultType.PMP_INSTRUCTION_FAULT,
            AccessFaultType.ATOMIC_OPERATION_FAULT,
        ]
        return random.choice(fault_types)
    
    def _generate_instruction_access_fault(self):
        """Generate an instruction access fault by jumping to PMP hole using JALR."""
        AR.comment("Attempting instruction fetch from PMP hole (riscv-dv pattern)")
        
        addr_reg = self.test_registers[0]
        
        # Get the ecall magic register for return address (following riscv-dv pattern)
        # This register will be used by the trap handler to resume execution
        ecall_reg = Configuration.RiscvConfig.ecall_arg_reg
        
        # Load address of PMP hole (fixed address from test_boot.py)
        AsmLogger.asm(f"li {addr_reg}, 0x{self.pmp_hole_base_addr:08x}", comment="Load PMP hole address")
        
        # Use JALR with ecall magic register as rd so trap handler knows where to return
        # This follows riscv-dv's pattern: JALR with rd=cfg.gpr[2] (ecall register)
        AsmLogger.asm(f"jalr {ecall_reg.name}, {addr_reg}, 0  # Jump to PMP hole - will fault, return addr in {ecall_reg.name}")
    
    def _generate_load_access_fault(self):
        """Generate a load access fault by reading from PMP hole."""
        AR.comment("Attempting load from PMP hole")
        
        addr_reg = self.test_registers[0]
        data_reg = self.test_registers[1]
        
        # Load address of PMP hole (fixed address from test_boot.py)
        AsmLogger.asm(f"li {addr_reg}, 0x{self.pmp_hole_base_addr:08x}", comment="Load PMP hole address")
        
        # Attempt various load operations
        load_ops = ["lb", "lh", "lw", "ld"]
        load_op = random.choice(load_ops)
        
        AsmLogger.asm(f"{load_op} {data_reg}, 0({addr_reg})  # Load from PMP hole - will fault")
    
    def _generate_store_access_fault(self):
        """Generate a store access fault by writing to PMP hole."""
        AR.comment("Attempting store to PMP hole")
        
        addr_reg = self.test_registers[0]
        data_reg = self.test_registers[1]
        
        # Load address of PMP hole (fixed address from test_boot.py)
        AsmLogger.asm(f"li {addr_reg}, 0x{self.pmp_hole_base_addr:08x}", comment="Load PMP hole address")
        
        # Load test data
        AsmLogger.asm(f"li {data_reg}, 0xCAFEBABE")
        
        # Attempt various store operations
        store_ops = ["sb", "sh", "sw", "sd"]
        store_op = random.choice(store_ops)
        
        AsmLogger.asm(f"{store_op} {data_reg}, 0({addr_reg})  # Store to PMP hole - will fault")
    
    def _generate_atomic_access_fault(self):
        """Generate an atomic operation access fault."""
        AR.comment("Attempting atomic operation on restricted memory")
        
        addr_reg = self.test_registers[0]
        data_reg = self.test_registers[1]
        result_reg = self.test_registers[2]
        
        # Load address of restricted memory
        AsmLogger.asm(f"la {addr_reg}, {self.restricted_memory.unique_label}")
        
        # Load test data
        AsmLogger.asm(f"li {data_reg}, 42")
        
        # Attempt various atomic operations
        amo_ops = ["amoswap.w", "amoadd.w", "amoand.w", "amoor.w", "amoxor.w"]
        amo_op = random.choice(amo_ops)
        
        AsmLogger.asm(f"{amo_op} {result_reg}, {data_reg}, ({addr_reg})  # AMO on restricted memory - will fault")
    
    def _generate_pmp_recovery_handler(self):
        """
        Generate PMP exception recovery code that modifies PMP configuration
        to allow access and continue execution. Based on riscv-dv recovery logic.
        """
        AR.comment("PMP fault recovery handler")
        
        scratch_regs = self.test_registers[:3]
        cause_reg, addr_reg, cfg_reg = scratch_regs
        
        # This would be called from the exception handler
        # Read mcause to determine fault type
        AsmLogger.asm(f"csrr {cause_reg}, mcause")
        
        # Read mtval to get faulting address
        AsmLogger.asm(f"csrr {addr_reg}, mtval")
        
        # Find matching PMP entry and enable appropriate access bit
        AsmLogger.asm(f"csrr {cfg_reg}, 0x{self.pmpcfg_csrs[0]:03x}")
        
        # Check fault type and enable appropriate permission
        # For instruction fault: set X bit
        # For load fault: set R bit  
        # For store fault: set W bit
        
        # Simplified recovery: enable all permissions (R+W+X = 0x7)
        AsmLogger.asm(f"ori {cfg_reg}, {cfg_reg}, 0x7", comment="Enable R+W+X permissions")
        AsmLogger.asm(f"csrw 0x{self.pmpcfg_csrs[0]:03x}, {cfg_reg}")
        
        AR.comment("PMP permissions updated - access should now succeed")
    
    def get_restricted_memory_info(self) -> Dict[str, Any]:
        """Get information about the PMP hole region."""
        return {
            'address': f"0x{self.pmp_hole_base_addr:08x}",
            'size': self.pmp_hole_size,
            'type': 'PMP hole (no RWX permissions)',
        }
    
    def get_pmp_configuration(self) -> List[Dict[str, Any]]:
        """Get the current PMP configuration."""
        return self.pmp_regions.copy()
    
    @staticmethod
    def generate_pmp_setup_code(memory_region: MemoryManager.Memory,
                               access_permissions: str = "",
                               locked: bool = True) -> List[str]:
        """
        Static method to generate PMP setup code for a memory region.
        
        Args:
            memory_region: The memory region to protect
            access_permissions: String of permissions ("r", "w", "x")
            locked: Whether to lock the PMP entry
            
        Returns:
            List of assembly instructions for PMP setup
        """
        instructions = []
        
        # This is a utility method that could be used by other ingredients
        # or templates to set up PMP regions
        
        instructions.append(f"# Setting up PMP for {memory_region.unique_label}")
        instructions.append(f"la t0, {memory_region.unique_label}")
        instructions.append(f"addi t1, t0, {memory_region.byte_size}")
        instructions.append("srli t1, t1, 2  # Convert to PMP address format")
        instructions.append("csrw pmpaddr0, t1")
        
        # Build configuration byte
        cfg_val = PMPAddressMode.TOR.value << 3  # TOR mode
        if "r" in access_permissions:
            cfg_val |= 1
        if "w" in access_permissions:
            cfg_val |= 2
        if "x" in access_permissions:
            cfg_val |= 4
        if locked:
            cfg_val |= 0x80
        
        instructions.append(f"li t0, {cfg_val}")
        instructions.append("csrw pmpcfg0, t0")
        instructions.append("# PMP setup complete")
        
        return instructions