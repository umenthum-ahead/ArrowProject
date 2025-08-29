"""
Illegal Instruction Ingredient for Exception Testing

Generates illegal instructions based on current ISA extensions, privilege mode,
and configuration. Ported from riscv-dv illegal instruction generation logic.

RISC-V Only: This ingredient is specifically designed for RISC-V architecture.
"""

import random
from typing import List, Optional, Dict, Any
from enum import Enum

from Arrow.Arrow_API import AR
from Arrow.Arrow_API import AR
from Arrow.Utils.configuration_management import Configuration
from Arrow.Tool.exception_management import ExceptionType, IllegalInstructionType
from Arrow.Tool.asm_libraries.asm_logger import AsmLogger


class IllegalInstructionType(Enum):
    """Types of illegal instructions to generate (from riscv-dv)"""
    ILLEGAL_OPCODE = "illegal_opcode"
    ILLEGAL_COMPRESSED_OPCODE = "illegal_compressed_opcode"  
    ILLEGAL_FUNC3 = "illegal_func3"
    ILLEGAL_FUNC7 = "illegal_func7"
    RESERVED_COMPRESSED = "reserved_compressed"
    HINT_INSTRUCTION = "hint_instruction"
    ILLEGAL_SYSTEM = "illegal_system"


@AR.ingredient_decorator
class IllegalInstructionIngredient(AR.Ingredient):
    """
    Ingredient that generates various types of illegal instructions for
    exception testing, with proper architecture and extension awareness.
    """
    
    def __init__(self, 
                 illegal_type: Optional[IllegalInstructionType] = None,
                 count: int = 5,
                 enable_compressed: bool = True):
        """
        Initialize the illegal instruction ingredient.
        
        Args:
            illegal_type: Specific type of illegal instruction (None for random)
            count: Number of illegal instructions to generate
            enable_compressed: Whether to generate compressed illegal instructions
        """
        # Validate RISC-V architecture
        if not Configuration.Architecture.riscv:
            raise RuntimeError(
                "Illegal instruction testing is only supported for RISC-V architecture. "
                f"Current architecture: {Configuration.Architecture.get_current()}"
            )
        
        self.name = "illegal_instruction_ingredient"
        self.illegal_type = illegal_type
        self.count = count
        self.enable_compressed = enable_compressed and self._is_compressed_supported()
        
        # Legal opcodes for RV32I/RV64I (from riscv-dv)
        self.legal_opcodes = [
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
        
        # Legal compressed opcodes by quadrant
        self.legal_compressed_opcodes = {
            0: [0b000, 0b010, 0b110],  # C0 quadrant
            1: [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],  # C1
            2: [0b000, 0b010, 0b100, 0b110],  # C2 quadrant
        }
        
        self.generated_instructions = []
    
    def init(self):
        """Initialize ingredient resources."""
        AR.comment(f"Initializing {self.name}")
    
    def body(self):
        """Generate illegal instructions."""
        AR.comment(f"Generating {self.count} illegal instructions")
        
        for i in range(self.count):
            illegal_type = self.illegal_type or self._choose_random_type()
            instr_word = self._generate_illegal_instruction(illegal_type)
            
            # Generate the illegal instruction as a .word directive
            AR.comment(f"Illegal instruction {i+1}: {illegal_type.value}")
            AsmLogger.asm(f".word 0x{instr_word:08x}  # {illegal_type.value}")
            
            # Add some spacing for readability
            if i < self.count - 1:
                AsmLogger.asm("nop  # Padding after illegal instruction")
            
            yield  # Important: yield for proper state management
        
        AR.comment(f"Generated {len(self.generated_instructions)} illegal instructions")
    
    def final(self):
        """Clean up ingredient resources."""
        AR.comment(f"Finalizing {self.name}")
        self.generated_instructions.clear()
    
    def _is_compressed_supported(self) -> bool:
        """Check if compressed instructions are supported."""
        # This would need to be integrated with Arrow's ISA configuration
        # For now, assume compressed is supported if RISC-V is enabled
        return True  # TODO: Check actual ISA configuration
    
    def _choose_random_type(self) -> IllegalInstructionType:
        """Choose a random illegal instruction type with weighted distribution."""
        # Distribution based on riscv-dv constraints
        type_weights = {
            IllegalInstructionType.ILLEGAL_OPCODE: 3,
            IllegalInstructionType.ILLEGAL_FUNC3: 1,
            IllegalInstructionType.ILLEGAL_FUNC7: 1,
            IllegalInstructionType.ILLEGAL_SYSTEM: 3,
        }
        
        if self.enable_compressed:
            type_weights.update({
                IllegalInstructionType.ILLEGAL_COMPRESSED_OPCODE: 1,
                IllegalInstructionType.RESERVED_COMPRESSED: 1,
                IllegalInstructionType.HINT_INSTRUCTION: 3,
            })
        
        # Weighted random choice
        types = list(type_weights.keys())
        weights = list(type_weights.values())
        return random.choices(types, weights=weights)[0]
    
    def _generate_illegal_instruction(self, illegal_type: IllegalInstructionType) -> int:
        """
        Generate a specific type of illegal instruction.
        
        Args:
            illegal_type: The type of illegal instruction to generate
            
        Returns:
            32-bit instruction word
        """
        if illegal_type == IllegalInstructionType.ILLEGAL_OPCODE:
            return self._generate_illegal_opcode()
        elif illegal_type == IllegalInstructionType.ILLEGAL_FUNC3:
            return self._generate_illegal_func3()
        elif illegal_type == IllegalInstructionType.ILLEGAL_FUNC7:
            return self._generate_illegal_func7()
        elif illegal_type == IllegalInstructionType.ILLEGAL_SYSTEM:
            return self._generate_illegal_system()
        elif illegal_type == IllegalInstructionType.ILLEGAL_COMPRESSED_OPCODE:
            return self._generate_illegal_compressed_opcode()
        elif illegal_type == IllegalInstructionType.RESERVED_COMPRESSED:
            return self._generate_reserved_compressed()
        elif illegal_type == IllegalInstructionType.HINT_INSTRUCTION:
            return self._generate_hint_instruction()
        else:
            raise ValueError(f"Unsupported illegal instruction type: {illegal_type}")
    
    def _generate_illegal_opcode(self) -> int:
        """Generate instruction with illegal opcode."""
        # Generate a random opcode that's not in the legal set
        while True:
            opcode = random.randint(0, 0x7F)
            if opcode not in self.legal_opcodes and (opcode & 0x3) == 0x3:
                break
        
        # Generate random fields for the rest of the instruction
        func3 = random.randint(0, 0x7)
        func7 = random.randint(0, 0x7F)
        rs1 = random.randint(0, 31)
        rs2 = random.randint(0, 31)
        rd = random.randint(0, 31)
        
        instr = (func7 << 25) | (rs2 << 20) | (rs1 << 15) | (func3 << 12) | (rd << 7) | opcode
        return instr
    
    def _generate_illegal_func3(self) -> int:
        """Generate instruction with illegal func3 field."""
        # Use a legal opcode but illegal func3
        opcode = random.choice([op for op in self.legal_opcodes if self._opcode_has_func3(op)])
        
        # Generate illegal func3 for this opcode
        legal_func3_values = self._get_legal_func3_values(opcode)
        while True:
            func3 = random.randint(0, 0x7)
            if func3 not in legal_func3_values:
                break
        
        # Generate random fields
        func7 = random.randint(0, 0x7F)
        rs1 = random.randint(0, 31)
        rs2 = random.randint(0, 31)
        rd = random.randint(0, 31)
        
        instr = (func7 << 25) | (rs2 << 20) | (rs1 << 15) | (func3 << 12) | (rd << 7) | opcode
        return instr
    
    def _generate_illegal_func7(self) -> int:
        """Generate instruction with illegal func7 field."""
        # Use opcodes that have func7 fields
        opcodes_with_func7 = [0b0110011, 0b0111011]  # OP, OP-32
        opcode = random.choice(opcodes_with_func7)
        
        # Use a legal func3 but illegal func7
        legal_func3_values = self._get_legal_func3_values(opcode)
        func3 = random.choice(legal_func3_values)
        
        # Generate illegal func7
        legal_func7_values = self._get_legal_func7_values(opcode, func3)
        while True:
            func7 = random.randint(0, 0x7F)
            if func7 not in legal_func7_values:
                break
        
        # Generate random fields
        rs1 = random.randint(0, 31)
        rs2 = random.randint(0, 31)
        rd = random.randint(0, 31)
        
        instr = (func7 << 25) | (rs2 << 20) | (rs1 << 15) | (func3 << 12) | (rd << 7) | opcode
        return instr
    
    def _generate_illegal_system(self) -> int:
        """Generate illegal SYSTEM instruction."""
        opcode = 0b1110011  # SYSTEM opcode
        
        func3 = random.randint(0, 0x7)
        
        if func3 == 0b000:
            # ECALL/EBREAK/xRET/WFI - make illegal by using non-zero rs1 and rd
            rs1 = random.randint(1, 31)  # Should be 0 for legal instructions
            rd = random.randint(1, 31)   # Should be 0 for legal instructions
            
            # Use invalid upper 12 bits
            invalid_imm_values = [
                0x003, 0x004, 0x005, 0x103, 0x104, 0x202, 0x303, 0x402, 0x502, 0x7b3
            ]
            imm = random.choice(invalid_imm_values)
            
            instr = (imm << 20) | (rs1 << 15) | (func3 << 12) | (rd << 7) | opcode
        else:
            # CSR instruction - use invalid CSR address
            # Generate a CSR address that doesn't exist
            invalid_csr = random.choice([0x800, 0x801, 0x802, 0xC20, 0xC21, 0xC22])
            rs1 = random.randint(0, 31)
            rd = random.randint(0, 31)
            
            instr = (invalid_csr << 20) | (rs1 << 15) | (func3 << 12) | (rd << 7) | opcode
        
        return instr
    
    def _generate_illegal_compressed_opcode(self) -> int:
        """Generate compressed instruction with illegal opcode."""
        if not self.enable_compressed:
            return self._generate_illegal_opcode()
        
        # Generate 16-bit compressed instruction with illegal quadrant/func3 combination
        quadrant = random.randint(0, 2)  # Avoid 11 which is for 32-bit instructions
        
        # Use illegal func3 for this quadrant
        legal_func3_values = self.legal_compressed_opcodes[quadrant]
        while True:
            func3 = random.randint(0, 0x7)
            if func3 not in legal_func3_values:
                break
        
        # Generate random fields for the compressed instruction
        fields = random.randint(0, 0x1FFF)  # 13 bits
        
        instr_16 = (func3 << 13) | (fields << 2) | quadrant
        # Pad to 32 bits (compressed instructions are 16-bit but we store as 32-bit)
        return instr_16
    
    def _generate_reserved_compressed(self) -> int:
        """Generate reserved compressed instruction."""
        if not self.enable_compressed:
            return self._generate_illegal_opcode()
        
        # C.ADDI16SP with nzimm=0 is reserved
        # Format: 011 | nzimm[9] | 2 | nzimm[4|6|8:7|5] | 01
        instr_16 = (0b011 << 13) | (0b10 << 7) | 0b01  # nzimm=0 makes it reserved
        return instr_16
    
    def _generate_hint_instruction(self) -> int:
        """Generate HINT instruction (legal but implementation-defined behavior)."""
        if not self.enable_compressed:
            # Generate 32-bit HINT (ADDI x0, x0, imm with non-zero imm)
            imm = random.randint(1, 0xFFF)  # Non-zero immediate
            return (imm << 20) | (0 << 15) | (0b000 << 12) | (0 << 7) | 0b0010011
        
        # Generate compressed HINT instruction
        # C.MV x0, rs2 (where rs2 != 0) is a HINT
        rs2 = random.randint(1, 31)  # Non-zero rs2
        instr_16 = (0b100 << 12) | (0 << 7) | (rs2 << 2) | 0b10
        return instr_16
    
    def _opcode_has_func3(self, opcode: int) -> bool:
        """Check if an opcode uses func3 field."""
        opcodes_with_func3 = [
            0b0000011,  # LOAD
            0b0001111,  # MISC-MEM
            0b0010011,  # OP-IMM
            0b0100011,  # STORE
            0b1100011,  # BRANCH
            0b0110011,  # OP
            0b1100111,  # JALR
            0b1110011,  # SYSTEM
        ]
        return opcode in opcodes_with_func3
    
    def _get_legal_func3_values(self, opcode: int) -> List[int]:
        """Get legal func3 values for a given opcode."""
        # Simplified mapping - in reality this would be more comprehensive
        func3_map = {
            0b0000011: [0b000, 0b001, 0b010, 0b100, 0b101, 0b110],  # LOAD
            0b0010011: [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],  # OP-IMM
            0b0100011: [0b000, 0b001, 0b010],  # STORE
            0b1100011: [0b000, 0b001, 0b100, 0b101, 0b110, 0b111],  # BRANCH
            0b0110011: [0b000, 0b001, 0b010, 0b011, 0b100, 0b101, 0b110, 0b111],  # OP
            0b1100111: [0b000],  # JALR
            0b1110011: [0b000, 0b001, 0b010, 0b011, 0b101, 0b110, 0b111],  # SYSTEM
        }
        return func3_map.get(opcode, [])
    
    def _get_legal_func7_values(self, opcode: int, func3: int) -> List[int]:
        """Get legal func7 values for a given opcode and func3."""
        # Simplified mapping for basic instructions
        if opcode == 0b0110011:  # OP
            if func3 in [0b000, 0b101]:  # ADD/SUB, SRL/SRA
                return [0b0000000, 0b0100000]
            else:
                return [0b0000000]
        elif opcode == 0b0111011:  # OP-32 (RV64)
            if func3 in [0b000, 0b101]:  # ADDW/SUBW, SRLW/SRAW
                return [0b0000000, 0b0100000]
            else:
                return [0b0000000]
        
        return [0b0000000]  # Default
    
    def get_generated_count(self) -> int:
        """Get the number of generated illegal instructions."""
        return len(self.generated_instructions)
    
    def get_instruction_types_used(self) -> List[str]:
        """Get the types of illegal instructions generated."""
        return [instr['type'] for instr in self.generated_instructions]