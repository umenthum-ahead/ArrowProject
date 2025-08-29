"""
Atomic Operation (AMO) Fault Ingredient for Exception Testing

Generates atomic memory operations that can trigger access faults due to
PMP restrictions, alignment issues, or other access violations. Based on
riscv-dv AMO instruction testing patterns.

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
from Arrow.Tool.exception_management import ExceptionType
from Arrow.Tool.asm_libraries.asm_logger import AsmLogger


class AMOOperation(Enum):
    """Atomic memory operations"""
    AMOSWAP = "amoswap"
    AMOADD = "amoadd"
    AMOXOR = "amoxor"
    AMOAND = "amoand"
    AMOOR = "amoor"
    AMOMIN = "amomin"
    AMOMAX = "amomax"
    AMOMINU = "amominu" 
    AMOMAXU = "amomaxu"


class AMOWidth(Enum):
    """AMO operation widths"""
    W = "w"   # 32-bit
    D = "d"   # 64-bit


class AMOFaultType(Enum):
    """Types of AMO faults to generate"""
    ACCESS_FAULT = "access_fault"      # PMP or other access restriction
    ALIGNMENT_FAULT = "alignment_fault"  # Misaligned access
    RESERVED_FAULT = "reserved_fault"    # Reserved AMO combinations


@AR.ingredient_decorator 
class AMOFaultIngredient(AR.Ingredient):
    """
    Ingredient that generates atomic memory operations that can trigger
    various types of faults for comprehensive exception testing.
    """
    
    def __init__(self,
                 fault_type: Optional[AMOFaultType] = None,
                 amo_count: int = 5,
                 enable_lr_sc: bool = True,
                 setup_restricted_memory: bool = True):
        """
        Initialize the AMO fault ingredient.
        
        Args:
            fault_type: Specific type of AMO fault (None for random)
            amo_count: Number of AMO operations to generate
            enable_lr_sc: Whether to include LR/SC (load-reserved/store-conditional)
            setup_restricted_memory: Whether to set up PMP-restricted memory
        """
        # Validate RISC-V architecture
        if not Configuration.Architecture.riscv:
            raise RuntimeError(
                "AMO fault testing is only supported for RISC-V architecture. "
                f"Current architecture: {Configuration.Architecture.get_current()}"
            )
        
        self.name = "amo_fault_ingredient"
        self.fault_type = fault_type
        self.amo_count = amo_count
        self.enable_lr_sc = enable_lr_sc
        self.setup_restricted_memory = setup_restricted_memory
        
        # Memory regions for testing
        self.amo_memory = None
        self.restricted_memory = None
        self.misaligned_memory = None
        
        # Registers for AMO operations
        self.amo_registers = []
        
        # Supported AMO operations
        self.amo_operations = list(AMOOperation)
        
    def init(self):
        """Initialize ingredient resources and set up memory regions."""
        AR.comment(f"Initializing {self.name}")
        
        # Set up regular AMO memory region (aligned)
        self.amo_memory = MemoryManager.Memory(
            name="amo_test_memory",
            byte_size=1024,
            init_value=0x12345678
        )
        
        # Set up restricted memory (would need PMP configuration)
        if self.setup_restricted_memory:
            self.restricted_memory = MemoryManager.Memory(
                name="amo_restricted_memory",
                byte_size=512,
                init_value=0xDEADBEEF
            )
        
        # Set up misaligned memory region
        self.misaligned_memory = MemoryManager.Memory(
            name="amo_misaligned_memory",
            byte_size=512,
            init_value=0xCAFEBABE
        )
        
        # Reserve registers for AMO operations
        self.amo_registers = [
            RegisterManager.get_and_reserve() for _ in range(6)
        ]
        
        AR.comment("AMO memory regions and registers initialized")
    
    def body(self):
        """Generate AMO fault test sequences."""
        AR.comment(f"Generating {self.amo_count} AMO fault tests")
        
        for i in range(self.amo_count):
            fault_type = self.fault_type or self._choose_random_fault_type()
            
            AR.comment(f"AMO fault test {i+1}: {fault_type.value}")
            
            if fault_type == AMOFaultType.ACCESS_FAULT:
                self._generate_amo_access_fault()
            elif fault_type == AMOFaultType.ALIGNMENT_FAULT:
                self._generate_amo_alignment_fault()
            elif fault_type == AMOFaultType.RESERVED_FAULT:
                self._generate_amo_reserved_fault()
            
            # Include LR/SC sequences if enabled
            if self.enable_lr_sc and random.choice([True, False]):
                self._generate_lr_sc_sequence(fault_type)
            
            # Add spacing between operations
            AsmLogger.asm("nop  # AMO operation spacing")
            
            yield  # Important: yield for proper state management
    
    def final(self):
        """Clean up ingredient resources."""
        AR.comment(f"Finalizing {self.name}")
        
        # Free reserved registers
        for reg in self.amo_registers:
            RegisterManager.free(reg)
        
        self.amo_registers.clear()
    
    def _choose_random_fault_type(self) -> AMOFaultType:
        """Choose a random AMO fault type."""
        return random.choice(list(AMOFaultType))
    
    def _generate_amo_access_fault(self):
        """Generate AMO operation that causes access fault due to PMP."""
        AR.comment("AMO access fault - attempting AMO on restricted memory")
        
        if not self.restricted_memory:
            AR.comment("No restricted memory configured - using regular memory")
            memory_region = self.amo_memory
        else:
            memory_region = self.restricted_memory
        
        addr_reg = self.amo_registers[0]
        data_reg = self.amo_registers[1]
        result_reg = self.amo_registers[2]
        
        # Load address of restricted memory
        AsmLogger.asm(f"la {addr_reg}, {memory_region.unique_label}")
        
        # Load test data
        test_value = random.randint(1, 0xFFFFFFFF)
        AsmLogger.asm(f"li {data_reg}, {test_value}")
        
        # Choose random AMO operation and width
        amo_op = random.choice(self.amo_operations)
        width = random.choice(list(AMOWidth))
        
        # Generate the AMO instruction that should fault
        amo_instr = f"{amo_op.value}.{width.value}"
        AsmLogger.asm(f"{amo_instr} {result_reg}, {data_reg}, ({addr_reg})  # AMO on restricted memory - will fault")
    
    def _generate_amo_alignment_fault(self):
        """Generate misaligned AMO operation that causes alignment fault."""
        AR.comment("AMO alignment fault - misaligned atomic operation")
        
        addr_reg = self.amo_registers[0]
        data_reg = self.amo_registers[1]
        result_reg = self.amo_registers[2]
        offset_reg = self.amo_registers[3]
        
        # Load base address
        AsmLogger.asm(f"la {addr_reg}, {self.misaligned_memory.unique_label}")
        
        # Create misaligned address (not aligned to operation width)
        # For 32-bit operations, use 2-byte alignment (should be 4-byte aligned)
        # For 64-bit operations, use 4-byte alignment (should be 8-byte aligned)
        width = random.choice(list(AMOWidth))
        if width == AMOWidth.W:
            misalign_offset = 2  # 32-bit ops need 4-byte alignment
        else:  # AMOWidth.D
            misalign_offset = 4  # 64-bit ops need 8-byte alignment
        
        AsmLogger.asm(f"addi {addr_reg}, {addr_reg}, {misalign_offset}", 
                     comment=f"Create misaligned address for {width.value}-bit AMO")
        
        # Load test data
        AsmLogger.asm(f"li {data_reg}, 0xABCDEF01")
        
        # Choose AMO operation
        amo_op = random.choice(self.amo_operations)
        amo_instr = f"{amo_op.value}.{width.value}"
        
        AsmLogger.asm(f"{amo_instr} {result_reg}, {data_reg}, ({addr_reg})  # Misaligned AMO - will fault")
    
    def _generate_amo_reserved_fault(self):
        """Generate reserved/illegal AMO instruction combinations."""
        AR.comment("AMO reserved fault - illegal AMO instruction encoding")
        
        addr_reg = self.amo_registers[0]
        
        # Load memory address
        AsmLogger.asm(f"la {addr_reg}, {self.amo_memory.unique_label}")
        
        # Generate illegal AMO instruction using .word directive
        # This creates an AMO-like instruction with invalid fields
        
        # RISC-V AMO instruction format:
        # [31:27] funct5, [26] aq, [25] rl, [24:20] rs2, [19:15] rs1, [14:12] funct3, [11:7] rd, [6:0] opcode
        
        # Start with valid AMO opcode (0101111 = 0x2F)
        opcode = 0b0101111
        
        # Use invalid funct5 combination
        invalid_funct5 = 0b11111  # Reserved funct5 value
        
        # Random other fields
        rs1 = self.amo_registers[0].get_register_number() if hasattr(self.amo_registers[0], 'get_register_number') else 5
        rs2 = self.amo_registers[1].get_register_number() if hasattr(self.amo_registers[1], 'get_register_number') else 6
        rd = self.amo_registers[2].get_register_number() if hasattr(self.amo_registers[2], 'get_register_number') else 7
        funct3 = 0b010  # Standard AMO funct3 for 32-bit
        
        # Construct illegal instruction
        illegal_instr = (
            (invalid_funct5 << 27) |  # Invalid funct5
            (0 << 26) |               # aq bit
            (0 << 25) |               # rl bit
            (rs2 << 20) |             # rs2
            (rs1 << 15) |             # rs1  
            (funct3 << 12) |          # funct3
            (rd << 7) |               # rd
            opcode                    # opcode
        )
        
        AsmLogger.asm(f".word 0x{illegal_instr:08x}  # Illegal AMO instruction")
    
    def _generate_lr_sc_sequence(self, fault_type: AMOFaultType):
        """Generate Load-Reserved/Store-Conditional sequence with faults."""
        AR.comment("LR/SC sequence with potential faults")
        
        addr_reg = self.amo_registers[0]
        data_reg = self.amo_registers[1]
        result_reg = self.amo_registers[2]
        temp_reg = self.amo_registers[3]
        
        # Choose memory region based on fault type
        if fault_type == AMOFaultType.ACCESS_FAULT and self.restricted_memory:
            memory_region = self.restricted_memory
        elif fault_type == AMOFaultType.ALIGNMENT_FAULT:
            memory_region = self.misaligned_memory
        else:
            memory_region = self.amo_memory
        
        # Load address
        AsmLogger.asm(f"la {addr_reg}, {memory_region.unique_label}")
        
        if fault_type == AMOFaultType.ALIGNMENT_FAULT:
            # Create misaligned address for LR/SC
            AsmLogger.asm(f"addi {addr_reg}, {addr_reg}, 2", 
                         comment="Misalign address for LR/SC")
        
        # Load-Reserved operation
        width = random.choice(list(AMOWidth))
        lr_instr = f"lr.{width.value}"
        AsmLogger.asm(f"{lr_instr} {data_reg}, ({addr_reg})  # Load-Reserved")
        
        # Modify the loaded value
        AsmLogger.asm(f"addi {temp_reg}, {data_reg}, 1", comment="Increment loaded value")
        
        # Store-Conditional operation
        sc_instr = f"sc.{width.value}"
        AsmLogger.asm(f"{sc_instr} {result_reg}, {temp_reg}, ({addr_reg})  # Store-Conditional")
        
        # Check SC result
        AsmLogger.asm(f"beqz {result_reg}, 1f", comment="Branch if SC succeeded")
        AsmLogger.asm("# SC failed - reservation was lost")
        AsmLogger.asm("1:")
    
    def _generate_amo_stress_sequence(self):
        """Generate stress test with multiple concurrent AMO operations."""
        AR.comment("AMO stress sequence - multiple atomic operations")
        
        addr_reg = self.amo_registers[0]
        
        # Load base address
        AsmLogger.asm(f"la {addr_reg}, {self.amo_memory.unique_label}")
        
        # Generate multiple AMO operations on the same location
        for i in range(3):
            data_reg = self.amo_registers[(i + 1) % len(self.amo_registers)]
            result_reg = self.amo_registers[(i + 2) % len(self.amo_registers)]
            
            # Load different test values
            test_value = 0x1000 + i * 0x111
            AsmLogger.asm(f"li {data_reg}, {test_value}")
            
            # Random AMO operation
            amo_op = random.choice(self.amo_operations)
            width = AMOWidth.W  # Use 32-bit for stress test
            
            amo_instr = f"{amo_op.value}.{width.value}"
            AsmLogger.asm(f"{amo_instr} {result_reg}, {data_reg}, ({addr_reg})")
            
            yield  # Allow other operations to interleave
    
    def get_memory_regions(self) -> Dict[str, Any]:
        """Get information about memory regions used for AMO testing."""
        regions = {}
        
        if self.amo_memory:
            regions['normal'] = {
                'label': self.amo_memory.unique_label,
                'size': self.amo_memory.byte_size,
                'purpose': 'Normal AMO operations'
            }
        
        if self.restricted_memory:
            regions['restricted'] = {
                'label': self.restricted_memory.unique_label,
                'size': self.restricted_memory.byte_size,
                'purpose': 'Access fault testing'
            }
        
        if self.misaligned_memory:
            regions['misaligned'] = {
                'label': self.misaligned_memory.unique_label,
                'size': self.misaligned_memory.byte_size,
                'purpose': 'Alignment fault testing'
            }
        
        return regions
    
    def get_supported_operations(self) -> List[str]:
        """Get list of supported AMO operations."""
        operations = []
        
        for op in self.amo_operations:
            for width in AMOWidth:
                operations.append(f"{op.value}.{width.value}")
        
        if self.enable_lr_sc:
            for width in AMOWidth:
                operations.extend([f"lr.{width.value}", f"sc.{width.value}"])
        
        return operations
    
    @staticmethod
    def generate_amo_test_data(count: int = 10) -> List[int]:
        """Generate test data values for AMO operations."""
        test_data = []
        
        # Include various interesting values
        interesting_values = [
            0x00000000,  # Zero
            0xFFFFFFFF,  # All ones
            0x80000000,  # Sign bit
            0x7FFFFFFF,  # Max positive
            0xAAAAAAAA,  # Alternating bits
            0x55555555,  # Alternating bits (inverse)
        ]
        
        test_data.extend(interesting_values)
        
        # Add random values
        while len(test_data) < count:
            test_data.append(random.randint(0, 0xFFFFFFFF))
        
        return test_data[:count]